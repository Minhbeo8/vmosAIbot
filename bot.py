#!/usr/bin/env python3
import asyncio, aiohttp, discord, json, logging, os, re, time
from discord.ext import commands
from dotenv import load_dotenv
from googletrans import Translator
from typing import Literal, List
from discord import app_commands

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Config:
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    OWNER_ID = 1370417047070048276 # ID của discord của bạn
    API_BASE_URL = 'https://api.vmoscloud.com/vcpcloud/api'
    POINTS_PER_IMAGE = 1000
    ACCOUNTS_FILE = 'accounts.json'
    PROMPT_CACHE_FILE = 'prompt_cache.json'

def is_owner():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == Config.OWNER_ID
    return app_commands.check(predicate)

class AccountManager:
    def __init__(self, file_path=Config.ACCOUNTS_FILE):
        self.file_path = file_path; self.accounts = []; self.current_index = -1
        self.reload()
    def reload(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f: self.accounts = json.load(f)
            if not self.accounts or not isinstance(self.accounts, list): raise ValueError("File rỗng hoặc không hợp lệ.")
            self.current_index = 0; logger.info(f"✅ Đã tải lại thành công {len(self.accounts)} tài khoản."); return True
        except FileNotFoundError: logger.error(f"❌ LỖI: Không tìm thấy file {self.file_path}."); self.accounts = []; return False
        except Exception as e: logger.error(f"❌ Lỗi khi đọc file accounts.json: {e}"); self.accounts = []; return False
    def get_current_account(self):
        if not self.accounts: return None
        return self.accounts[self.current_index]
    def switch_to_next_account(self):
        if not self.accounts: return None
        self.current_index = (self.current_index + 1) % len(self.accounts)
        logger.warning(f"🔄 Đã chuyển sang tài khoản: {self.get_current_account().get('description', f'#{self.current_index}')}")
        return self.get_current_account()

account_manager = AccountManager()
#--cache--
class PromptCache:
    def __init__(self, file_path=Config.PROMPT_CACHE_FILE):
        self.file_path = file_path; self.cache = self._load()
    def _load(self):
        if not os.path.exists(self.file_path): return {}
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f: return json.load(f)
        except (json.JSONDecodeError, IOError): return {}
    def _save(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f: json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except IOError as e: logger.error(f"❌ Không thể ghi file cache: {e}")
    def get(self, prompt_key: str): return self.cache.get(prompt_key)
    def set(self, prompt_key: str, image_url: str): self.cache[prompt_key] = image_url; self._save()

prompt_cache = PromptCache()

def get_vmos_headers(account):
    if not account: raise ValueError("Tài khoản không hợp lệ.")
    return {'Accept': 'application/json, text/plain, */*', 'Content-Type': 'application/json', 'Token': account['token'], 'userId': str(account['userId']), 'clientType': 'web', 'appVersion': '2008500', 'requestsource': 'wechat-miniapp', 'SupplierType': '0', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'}
STYLE_KEYWORDS = {"Không có": "best quality, masterpiece", "Anime": "anime artwork, anime style, key visual, vibrant, studio anime, highly detailed", "Thực tế (Realistic)": "photorealistic, realistic, 8k, ultra-detailed, professional photography, sharp focus, cinematic photo", "Cyberpunk": "cyberpunk style, neon lights, futuristic city, dystopian, cinematic, blade runner", "Fantasy": "fantasy art, magical, epic, enchanting, detailed matte painting, dungeons and dragons", "Tranh sơn dầu": "oil painting, masterpiece, textured, brush strokes, impressionism"}
ASPECT_RATIO_MAP = {"1:1 (Vuông)": "1024x1024", "3:4 (Dọc)": "768x1024", "4:3 (Ngang)": "1024x768", "16:9 (Màn ảnh rộng)": "1344x768", "9:16 (Story)": "768x1344"}

class VMOSAIBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default(); intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=intents, help_command=None)
        self.session, self.translator = None, Translator(); self.generation_queue = asyncio.Queue(); self.current_job_user = None
    async def setup_hook(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)); logger.info("🤖 VMOS AI Bot setup completed"); self.loop.create_task(self.generation_worker())
    async def on_ready(self):
        logger.info(f"🎨 {self.user} is online and ready!"); await self.tree.sync()
        activity_name = f"với {len(account_manager.accounts)} tài khoản" if account_manager.accounts else "Lỗi tài khoản"
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=activity_name))
    async def close(self):
        if self.session: await self.session.close(); await super().close()
    async def generation_worker(self):
        await self.wait_until_ready();
        if not account_manager.accounts: logger.error("🚫 Worker không thể khởi động vì không có tài khoản nào."); return
        logger.info("👷 Generation worker is now running.")
        while not self.is_closed():
            job = await self.generation_queue.get(); interaction, pd = job['interaction'], job['prompt_details']
            self.current_job_user = interaction.user; message = None
            try:
                cleaned_prompt = self.clean_prompt(pd['prompt']); core_prompt_parts = [cleaned_prompt]
                if pd['negative_prompt']: core_prompt_parts.append(f"| negative prompt: {self.clean_prompt(pd['negative_prompt'])}")
                core_prompt_for_cache = await self.translate_prompt(" ".join(core_prompt_parts)); cache_key = f"{core_prompt_for_cache}_{pd['size']}_{pd['guidance_scale']}_{pd['seed']}"
                cached_url = prompt_cache.get(cache_key)
                if cached_url:
                    logger.info(f"✅ Smart Cache Hit!"); success_embed = discord.Embed(title="✅ Tạo ảnh thành công! (từ bộ đệm)", color=0x00FF88); success_embed.add_field(name="📝 Prompt Gốc", value=f"```{cleaned_prompt}```", inline=False); success_embed.set_image(url=cached_url); success_embed.set_footer(text=f"Yêu cầu bởi {interaction.user.display_name} | Bot đã tiết kiệm 1000 điểm!", icon_url=interaction.user.avatar.url)
                    short_url = await self.shorten_url(cached_url); await interaction.followup.send(embed=success_embed, view=ImageView(short_url)); self.generation_queue.task_done(); self.current_job_user = None; continue
                final_prompt = self.enhance_prompt(cleaned_prompt, pd['style'], pd['negative_prompt']); translated_final_prompt = await self.translate_prompt(final_prompt)
                active_account = None; checked_accounts = 0
                while checked_accounts < len(account_manager.accounts):
                    current_acc = account_manager.get_current_account()
                    points_res = await self.get_points(current_acc)
                    if points_res.get('success') and points_res.get('points', 0) >= Config.POINTS_PER_IMAGE:
                        active_account = current_acc; break
                    else: account_manager.switch_to_next_account(); checked_accounts += 1
                if not active_account: raise Exception("Tất cả các tài khoản đều đã hết điểm.")
                embed = discord.Embed(title="🎨 Đang xử lý...", color=discord.Color.gold()); embed.set_footer(text=f"Sử dụng tài khoản: {active_account.get('description')}")
                message = await interaction.followup.send(embed=embed, wait=True)
                gen_result = await self.generate_image(translated_final_prompt, active_account, pd['size'], pd['guidance_scale'], pd['seed'])
                if not gen_result.get('success'): raise Exception(f"{gen_result.get('error')}")
                task_id = gen_result['task_id']
                status_result = await self.check_image_status(task_id, active_account)
                if not status_result.get('success'): raise Exception(f"{status_result.get('error')}")
                images = status_result.get('images', [])
                if not images or not images[0]: raise Exception("API không trả về ảnh.")
                image_url = images[0]; prompt_cache.set(cache_key, image_url); logger.info(f"💾 Đã lưu kết quả vào cache.")
                short_url = await self.shorten_url(image_url)
                success_embed = discord.Embed(title="✅ Tạo ảnh thành công!", color=0x00FF88); success_embed.add_field(name="📝 Prompt Gốc", value=f"```{cleaned_prompt}```", inline=False)
                if pd['style'] != "Không có": success_embed.add_field(name="✨ Phong cách", value=pd['style'], inline=True)
                success_embed.set_image(url=image_url); success_embed.set_footer(text=f"Yêu cầu bởi {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                await message.edit(embed=success_embed, view=ImageView(short_url))
            except Exception as e:
                logger.error(f"Error processing job: {e}", exc_info=False)
                error_embed = discord.Embed(title="❌ Tạo ảnh thất bại", description=str(e), color=0xFF4444)
                if message: await message.edit(embed=error_embed, view=None)
                else: await interaction.followup.send(embed=error_embed)
            finally: self.current_job_user = None; self.generation_queue.task_done()
    def enhance_prompt(self, prompt: str, style: str, negative_prompt: str | None) -> str:
        style_keywords = STYLE_KEYWORDS.get(style, ''); enhanced_prompt = f"{prompt}, {style_keywords}" if style_keywords else prompt
        if negative_prompt: final_prompt = f"{enhanced_prompt} | negative prompt: {self.clean_prompt(negative_prompt)}"
        else: final_prompt = enhanced_prompt
        return re.sub(r',\s*,', ',', final_prompt).strip(', ')
    async def shorten_url(self, long_url: str):
        try:
            async with self.session.get(f"http://tinyurl.com/api-create.php?url={long_url}") as r:
                if r.status == 200: return await r.text()
        except: pass
        return long_url
    async def translate_prompt(self, text: str):
        try:
            if self.translator.detect(text).lang not in ['en', 'zh-cn', 'zh-tw']: return self.translator.translate(text, dest='en').text
        except: pass
        return text
    async def generate_image(self, prompt: str, account: dict, size: str, guidance_scale: float, seed: int):
        payload = {'prompt': prompt, 'size': size, 'seed': seed, 'guidance_scale': guidance_scale};
        async with self.session.post(f"{Config.API_BASE_URL}/images/generation", json=payload, headers=get_vmos_headers(account)) as r:
            data = await r.json();
            if r.status == 200 and data.get('code') == 200 and (td := data.get('data')): return {'success': True, 'task_id': td.get('taskId')}
            return {'success': False, 'error': data.get('msg', f'HTTP {r.status}')}
    async def check_image_status(self, task_id: str, account: dict):
        url = f"{Config.API_BASE_URL}/images/status/{task_id}";
        for _ in range(90):
            await asyncio.sleep(2)
            try:
                async with self.session.get(url, headers=get_vmos_headers(account)) as r:
                    if r.status == 200 and (d := await r.json()).get('code') == 200 and (rd := d.get('data')): return {'success': True, 'images': json.loads(rd.get('returnImage', '[]'))}
            except: pass
        return {'success': False, 'error': 'Image generation timed out.'}
    async def get_points(self, account: dict):
        url = f"{Config.API_BASE_URL}/imagesUser/userInfo"
        try:
            async with self.session.post(url, json={}, headers=get_vmos_headers(account)) as r:
                data = await r.json()
                if r.status == 200 and data.get('code') == 200 and (ud := data.get('data')): return {'success': True, 'points': ud.get('remainingPoints', 0)}
            return {'success': False, 'error': data.get('msg', 'API Error')}
        except Exception as e: return {'success': False, 'error': str(e)}
    def clean_prompt(self, prompt: str): return re.sub(r'\s+', ' ', prompt.strip())

bot = VMOSAIBot()

class AddAccountModal(discord.ui.Modal, title='Thêm tài khoản VMOS mới'):
    token_input=discord.ui.TextInput(label='VMOS Token',placeholder='Dán token...',style=discord.TextStyle.short,required=True)
    userid_input=discord.ui.TextInput(label='User ID',placeholder='Dán User ID...',style=discord.TextStyle.short,required=True)
    description_input=discord.ui.TextInput(label='Mô tả (tùy chọn)',placeholder='Ví dụ: Tài khoản phụ 3...',style=discord.TextStyle.short,required=False)
    async def on_submit(self, interaction: discord.Interaction):
        token, user_id, desc = self.token_input.value.strip(), self.userid_input.value.strip(), self.description_input.value.strip()
        try:
            accounts_data = []
            if os.path.exists(Config.ACCOUNTS_FILE):
                with open(Config.ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                    try: accounts_data = json.load(f)
                    except json.JSONDecodeError: pass
            for acc in accounts_data:
                if acc.get('token') == token or acc.get('userId') == user_id: await interaction.response.send_message(f"❌ Lỗi: Token hoặc User ID này đã tồn tại.", ephemeral=True); return
            new_account = {"token": token, "userId": user_id, "description": desc if desc else f"Tài khoản #{len(accounts_data) + 1}"}
            accounts_data.append(new_account)
            with open(Config.ACCOUNTS_FILE, 'w', encoding='utf-8') as f: json.dump(accounts_data, f, indent=2, ensure_ascii=False)
            account_manager.reload()
            activity_name = f"với {len(account_manager.accounts)} tài khoản"
            await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=activity_name))
            await interaction.response.send_message(f"✅ Đã thêm thành công! Bot hiện quản lý **{len(accounts_data)}** tài khoản.", ephemeral=True)
        except Exception as e:
            logger.error(f"Lỗi khi thêm tài khoản: {e}", exc_info=True); await interaction.response.send_message(f"❌ Đã xảy ra lỗi. Vui lòng kiểm tra log.", ephemeral=True)

class EditAccountModal(discord.ui.Modal, title='Chỉnh sửa tài khoản VMOS'):
    def __init__(self, account_to_edit):
        super().__init__(); self.account_to_edit = account_to_edit
        self.token_input = discord.ui.TextInput(label='VMOS Token mới', default=account_to_edit.get('token', ''), style=discord.TextStyle.short, required=True)
        self.userid_input = discord.ui.TextInput(label='User ID mới', default=str(account_to_edit.get('userId', '')), style=discord.TextStyle.short, required=True)
        self.description_input = discord.ui.TextInput(label='Mô tả mới', default=account_to_edit.get('description', ''), style=discord.TextStyle.short, required=False)
        self.add_item(self.token_input); self.add_item(self.userid_input); self.add_item(self.description_input)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            with open(Config.ACCOUNTS_FILE, 'r+', encoding='utf-8') as f:
                accounts_data = json.load(f); acc_found = None
                for acc in accounts_data:
                    if acc['token'] == self.account_to_edit['token'] and str(acc['userId']) == str(self.account_to_edit['userId']):
                        acc['token'] = self.token_input.value.strip(); acc['userId'] = self.userid_input.value.strip(); acc['description'] = self.description_input.value.strip(); acc_found = acc; break
                if not acc_found: await interaction.response.send_message("❌ Không tìm thấy tài khoản gốc để cập nhật.", ephemeral=True); return
                f.seek(0); f.truncate(); json.dump(accounts_data, f, indent=2, ensure_ascii=False)
            account_manager.reload()
            await interaction.response.send_message(f"✅ Đã cập nhật tài khoản `{acc_found['description']}`.", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"❌ Lỗi khi cập nhật file: {e}", ephemeral=True)

class ImageView(discord.ui.View):
    def __init__(self, download_url: str):
        super().__init__(timeout=300)
        self.add_item(discord.ui.Button(label='Tải ảnh gốc', style=discord.ButtonStyle.link, emoji='📥', url=download_url))

@bot.tree.command(name='addaccount', description='(Chủ bot) Thêm một tài khoản VMOS mới.')
@is_owner()
async def add_account_command(interaction: discord.Interaction): await interaction.response.send_modal(AddAccountModal())

@bot.tree.command(name='editaccount', description='(Chủ bot) Chỉnh sửa một tài khoản VMOS.')
@is_owner()
@app_commands.describe(account='Chọn tài khoản cần sửa từ danh sách gợi ý.')
async def edit_account_command(interaction: discord.Interaction, account: str):
    account_to_edit = next((acc for acc in account_manager.accounts if acc.get('description') == account), None)
    if not account_to_edit: await interaction.response.send_message("❌ Không tìm thấy tài khoản.", ephemeral=True); return
    await interaction.response.send_modal(EditAccountModal(account_to_edit))
@edit_account_command.autocomplete('account')
async def edit_account_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    choices = [acc.get('description', f"Tài khoản không tên #{i}") for i, acc in enumerate(account_manager.accounts)]
    return [app_commands.Choice(name=choice, value=choice) for choice in choices if current.lower() in choice.lower()][:25]

@bot.tree.command(name='removeaccount', description='(Chủ bot) Xóa một tài khoản VMOS.')
@is_owner()
@app_commands.describe(account='Chọn tài khoản cần xóa từ danh sách gợi ý.')
async def remove_account_command(interaction: discord.Interaction, account: str):
    await interaction.response.defer(ephemeral=True)
    try:
        with open(Config.ACCOUNTS_FILE, 'r', encoding='utf-8') as f: accounts_data = json.load(f)
        original_count = len(accounts_data)
        accounts_data = [acc for acc in accounts_data if acc.get('description') != account]
        if len(accounts_data) == original_count: await interaction.followup.send("❌ Không tìm thấy tài khoản để xóa."); return
        with open(Config.ACCOUNTS_FILE, 'w', encoding='utf-8') as f: json.dump(accounts_data, f, indent=2, ensure_ascii=False)
        account_manager.reload()
        await interaction.followup.send(f"✅ Đã xóa tài khoản `{account}`. Bot còn lại {len(accounts_data)} tài khoản.")
    except Exception as e: await interaction.followup.send(f"❌ Lỗi khi xóa tài khoản: {e}")
@remove_account_command.autocomplete('account')
async def remove_account_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    choices = [acc.get('description', f"Tài khoản không tên #{i}") for i, acc in enumerate(account_manager.accounts)]
    return [app_commands.Choice(name=choice, value=choice) for choice in choices if current.lower() in choice.lower()][:25]

@bot.tree.command(name='generate', description='Tạo ảnh AI với đầy đủ tùy chọn chuyên nghiệp.')
@app_commands.describe(prompt='Mô tả chính của ảnh.',style='Chọn một phong cách nghệ thuật.',negative_prompt='Những thứ bạn KHÔNG muốn thấy trong ảnh.',aspect_ratio='Chọn tỷ lệ khung hình cho ảnh.',guidance_scale='Mức độ bám sát prompt (thấp = sáng tạo, cao = bám sát).',seed='Sử dụng một hạt giống cụ thể để tái tạo ảnh (-1 là ngẫu nhiên).')
async def generate_command(interaction: discord.Interaction, prompt: str, style: Literal["Không có", "Anime", "Thực tế (Realistic)", "Cyberpunk", "Fantasy", "Tranh sơn dầu"] = "Không có", aspect_ratio: Literal["1:1 (Vuông)", "3:4 (Dọc)", "4:3 (Ngang)", "16:9 (Màn ảnh rộng)", "9:16 (Story)"] = "1:1 (Vuông)", negative_prompt: str = None, guidance_scale: app_commands.Range[float, 1.0, 10.0] = 7.5, seed: app_commands.Range[int, -1, 2147483647] = -1):
    await interaction.response.defer(ephemeral=True)
    if not account_manager.accounts: await interaction.followup.send("❌ Bot chưa được cấu hình."); return
    queue_position = bot.generation_queue.qsize() + 1
    job = {'interaction': interaction, 'prompt_details': {'prompt': prompt, 'style': style, 'negative_prompt': negative_prompt, 'size': ASPECT_RATIO_MAP[aspect_ratio], 'guidance_scale': guidance_scale, 'seed': seed}}
    await bot.generation_queue.put(job)
    await interaction.followup.send(f"✅ Yêu cầu của bạn đã vào hàng đợi ở vị trí **#{queue_position}**.")

@bot.tree.command(name='queue', description='Xem hàng đợi tạo ảnh hiện tại.')
async def queue_command(interaction: discord.Interaction):
    queue_size = bot.generation_queue.qsize()
    embed = discord.Embed(title="🎨 Hàng đợi tạo ảnh", color=discord.Color.gold())
    if bot.current_job_user: embed.add_field(name="▶️ Đang xử lý", value=f"Yêu cầu của **{bot.current_job_user.display_name}**", inline=False)
    else: embed.add_field(name="▶️ Đang xử lý", value="Không có yêu cầu nào.", inline=False)
    embed.add_field(name="⏳ Đang chờ", value=f"Có **{queue_size}** yêu cầu khác trong hàng đợi.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='points', description='(Chủ bot) Kiểm tra điểm của tất cả các tài khoản.')
@is_owner()
async def points_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not account_manager.accounts: await interaction.followup.send("⚠️ Không có tài khoản nào được cấu hình."); return
    embed = discord.Embed(title="💎 Tình trạng điểm các tài khoản", color=0x00FF88)
    total_points = 0
    for i, acc in enumerate(account_manager.accounts):
        result = await bot.get_points(acc)
        status, points = ("✅", result.get('points', 0)) if result.get('success') else ("❌", f"Lỗi: {result.get('error')}")
        if isinstance(points, int): total_points += points
        is_current = " (hiện tại)" if i == account_manager.current_index else ""
        embed.add_field(name=f"{status} {acc.get('description', f'Tài khoản #{i+1}')}{is_current}", value=f"Điểm: **{points:,}**" if isinstance(points, int) else points, inline=False)
    embed.set_footer(text=f"Tổng số điểm khả dụng: {total_points:,}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='help', description='Hiển thị thông tin trợ giúp về bot.')
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Trợ giúp Bot VMOS AI", description="Một bot AI mạnh mẽ với đầy đủ tùy chọn chuyên nghiệp.", color=discord.Color.blue())
    embed.add_field(name="`/generate <prompt> [options...]`", value="Tạo ảnh AI với các tùy chọn nâng cao.", inline=False)
    embed.add_field(name="`/queue`", value="Xem trạng thái hàng đợi hiện tại.", inline=False)
    embed.add_field(name="`/points`", value="(Chủ bot) Kiểm tra số điểm của tất cả tài khoản.", inline=False)
    embed.add_field(name="`/addaccount`", value="(Chủ bot) Thêm tài khoản VMOS mới.", inline=False)
    embed.add_field(name="`/editaccount`", value="(Chủ bot) Sửa thông tin tài khoản.", inline=False)
    embed.add_field(name="`/removeaccount`", value="(Chủ bot) Xóa tài khoản.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

def main():
    if not Config.DISCORD_BOT_TOKEN: logger.error("❌ Thiếu DISCORD_BOT_TOKEN!"); return
    if not account_manager.accounts: logger.error("❌ Không thể khởi động bot vì `accounts.json` rỗng hoặc lỗi."); return
    logger.info("🚀 Starting VMOS AI Bot (Final Version)...")
    bot.run(Config.DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()
