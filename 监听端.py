import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import os
import logging
from datetime import datetime
import sys
from wxauto import WeChat
import requests
import json

# API 配置
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
LOCAL_API_URL = "http://localhost:5000/ai/ask"


class AnimatedButton(tk.Button):
    """自定义动画按钮"""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.default_bg = self["bg"]
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self["bg"] = self["activebackground"]

    def on_leave(self, e):
        self["bg"] = self.default_bg


class WeChatMessageLogger:
    def __init__(self, log_file_path, api_key, my_name):
        self.log_file_path = os.path.abspath(log_file_path)
        self.wx = WeChat()
        self.running = False
        self.listener_thread = None
        self.api_key = api_key
        self.my_name = my_name
        self.current_group = None
        self.reply_mode = "api"
        self._ensure_log_file()

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler('wechat_logger.log', encoding='utf-8')]
        )

    def _ensure_log_file(self):
        """确保日志文件存在"""
        if not os.path.exists(self.log_file_path):
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("微信消息日志文件\n")
                f.write("=" * 50 + "\n\n")

    def update_log_header(self, group_name):
        """更新日志文件头部信息"""
        try:
            with open(self.log_file_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                f.seek(0, 0)
                f.write(f"监听群聊: {group_name}\n")
                f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                f.write(content)
        except Exception as e:
            logging.error(f"更新日志头部信息失败: {str(e)}")

    def call_deepseek_api(self, prompt):
        """调用DeepSeek API"""
        if not self.api_key:
            logging.warning("未提供API密钥")
            return "抱歉，我还没有配置API密钥，无法回答你的问题。"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "你是一个微信聊天助手，请用简洁友好的方式回复用户的问题。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'] if 'choices' in result else "抱歉，我无法理解这个问题。"
        except Exception as e:
            logging.error(f"API调用失败: {str(e)}")
            return "处理回复时发生错误，请稍后再试。"

    def call_local_api(self, prompt):
        """调用本地服务器API"""
        try:
            response = requests.post(
                LOCAL_API_URL,
                json={'question': prompt},
                timeout=30
            )
            response.raise_for_status()
            return response.json()["reply"]
        except requests.exceptions.RequestException as e:
            logging.error(f"本地API调用失败: {str(e)}")
            return "无法连接到本地AI服务，请检查服务器是否运行。"
        except KeyError:
            logging.error("本地API返回格式不正确")
            return "本地AI服务返回格式不正确。"

    def start_listening(self, group_name, log_callback=None):
        """开始监听指定群聊"""
        if self.running:
            if log_callback:
                log_callback("[警告] 监听已经在运行中")
            return

        self.current_group = group_name
        self.running = True
        self.update_log_header(group_name)

        # 使用wxauto的官方监听方式
        self.wx.AddListenChat(
            nickname=group_name,
            callback=lambda msg, chat: self.on_message(msg, chat, log_callback))

        if log_callback:
            log_callback(f"[系统] 开始监听群聊: {group_name}")

    def stop_listening(self):
        """停止监听"""
        if self.running:
            self.running = False
            # wxauto没有提供直接的停止监听方法，我们通过标志位控制
            self.current_group = None

    def on_message(self, msg, chat, log_callback):
        """消息回调函数 - 适配wxauto消息对象"""
        if not self.running:
            return

        try:
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            # 使用wxauto消息对象的属性
            sender = getattr(msg, 'sender', getattr(msg, 'sendername', '未知发送人'))
            content = getattr(msg, 'content', str(msg))
            chat_name = self.current_group or '未知群聊'

            console_output = f"[{current_time}] [{chat_name}] [{sender}]: {content}"
            log_entry = f"时间: {current_time}\n"
            log_entry += f"群聊: {chat_name}\n"
            log_entry += f"发送人: {sender}\n"
            log_entry += f"内容: {content}\n"
            log_entry += "-" * 50 + "\n\n"

            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(log_entry)

            logging.info(f"消息已记录: {sender} -> {chat_name}")

            if log_callback:
                log_callback(console_output)

            # 处理特殊命令
            if content.strip() == "/local chat":
                self.reply_mode = "local"
                reply_msg = "已切换到本地服务器回复模式"
                self.wx.SendMsg(reply_msg, who=chat_name)
                log_callback(f"[系统] {reply_msg}")
                return
            elif content.strip() == "/api chat":
                self.reply_mode = "api"
                reply_msg = "已切换到API回复模式"
                self.wx.SendMsg(reply_msg, who=chat_name)
                log_callback(f"[系统] {reply_msg}")
                return
            elif content.strip() == "/help":
                help_msg = (
                    "可用命令:\n"
                    "/api chat - 切换到API回复模式\n"
                    "/local chat - 切换到本地AI回复模式\n"
                    "/help - 显示帮助信息"
                )
                self.wx.SendMsg(help_msg, who=chat_name)
                log_callback(f"[系统] 已发送帮助信息")
                return

            if f"@{self.my_name}" in content:
                logging.info(f"检测到@消息，来自: {sender}")
                if log_callback:
                    log_callback(f"[系统] 检测到@{self.my_name}，正在生成回复...")

                threading.Thread(
                    target=self.handle_mention_reply,
                    args=(sender, content, log_callback, chat_name),
                    daemon=True
                ).start()

        except Exception as e:
            error_details = f"处理消息时出错: {str(e)}. "
            error_details += f"消息类型: {type(msg)}"
            logging.error(error_details)
            if log_callback:
                log_callback(f"[错误] {error_details}")

    def handle_mention_reply(self, sender, content, log_callback, chat_name=None):
        """处理@消息并回复"""
        try:
            question = content.replace(f"@{self.my_name}", "").strip()
            chat_name = chat_name or self.current_group

            if self.reply_mode == "local":
                reply = self.call_local_api(question)
            else:
                reply = self.call_deepseek_api(question)

            formatted_reply = f"@{sender} {reply}"

            if chat_name:
                self.wx.SendMsg(formatted_reply, who=chat_name)
                log_msg = f"[系统] 已回复@{sender}: {reply[:50]}..."
            else:
                log_msg = f"[错误] 无法发送回复，当前群聊未设置"

            logging.info(log_msg)
            if log_callback:
                log_callback(log_msg)
        except Exception as e:
            error_msg = f"回复消息时出错: {str(e)}"
            logging.error(error_msg)
            if log_callback:
                log_callback(f"[错误] {error_msg}")

    def keep_running(self):
        """保持微信运行"""
        while True:
            try:
                self.wx.KeepRunning()
                time.sleep(1)
            except Exception as e:
                logging.error(f"保持微信运行时出错: {str(e)}")
                time.sleep(5)


class WeChatListenerUI:
    def __init__(self, master):
        self.master = master
        master.title("微信AI助手")
        master.geometry("800x600")

        # 初始化日志器
        self.logger = None

        # 创建UI元素
        self.create_widgets()

    def create_widgets(self):
        # 配置区域
        config_frame = ttk.LabelFrame(self.master, text="配置", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        # API密钥输入
        ttk.Label(config_frame, text="DeepSeek API密钥:").grid(row=0, column=0, sticky=tk.W)
        self.api_key_entry = ttk.Entry(config_frame, width=50)
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=5)

        # 我的微信昵称
        ttk.Label(config_frame, text="我的微信昵称:").grid(row=1, column=0, sticky=tk.W)
        self.my_name_entry = ttk.Entry(config_frame, width=30)
        self.my_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        # 日志文件路径
        ttk.Label(config_frame, text="日志文件路径:").grid(row=2, column=0, sticky=tk.W)
        self.log_path_entry = ttk.Entry(config_frame, width=50)
        self.log_path_entry.grid(row=2, column=1, padx=5, pady=5)
        self.log_path_entry.insert(0, "wechat_messages.log")

        # 监听群聊名称
        ttk.Label(config_frame, text="监听群聊名称:").grid(row=3, column=0, sticky=tk.W)
        self.group_name_entry = ttk.Entry(config_frame, width=30)
        self.group_name_entry.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)

        # 按钮区域
        button_frame = ttk.Frame(self.master)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        self.start_btn = AnimatedButton(
            button_frame,
            text="开始监听",
            command=self.start_listening,
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049"
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = AnimatedButton(
            button_frame,
            text="停止监听",
            command=self.stop_listening,
            bg="#f44336",
            fg="white",
            activebackground="#d32f2f"
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.help_btn = AnimatedButton(
            button_frame,
            text="帮助",
            command=self.show_help,
            bg="#2196F3",
            fg="white",
            activebackground="#0b7dda"
        )
        self.help_btn.pack(side=tk.LEFT, padx=5)

        # 日志显示区域
        log_frame = ttk.LabelFrame(self.master, text="日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def start_listening(self):
        """开始监听按钮事件"""
        api_key = self.api_key_entry.get().strip()
        my_name = self.my_name_entry.get().strip()
        log_path = self.log_path_entry.get().strip()
        group_name = self.group_name_entry.get().strip()

        if not all([api_key, my_name, log_path, group_name]):
            messagebox.showerror("错误", "请填写所有必填字段!")
            return

        if not self.logger:
            self.logger = WeChatMessageLogger(log_path, api_key, my_name)
            # 启动保持微信运行的线程
            threading.Thread(
                target=self.logger.keep_running,
                daemon=True
            ).start()

        self.logger.start_listening(group_name, self.log_callback)
        self.log_callback(f"[系统] 正在启动监听: {group_name}")
        self.log_callback(f"[系统] 在群聊中输入 '/help' 查看可用命令")

    def stop_listening(self):
        """停止监听按钮事件"""
        if hasattr(self, 'logger') and self.logger:
            self.logger.stop_listening()
            self.log_callback("[系统] 已停止监听")

    def show_help(self):
        """显示帮助信息"""
        help_window = tk.Toplevel(self.master)
        help_window.title("使用帮助")
        help_window.geometry("600x400")

        help_text = """
        ========== 微信AI助手 使用说明 ==========

        1. 配置信息:
          - DeepSeek API密钥: 从DeepSeek官网获取的API密钥
          - 我的微信昵称: 在微信中使用的昵称
          - 日志文件路径: 消息日志保存的文件路径
          - 监听群聊名称: 要监听的微信群聊名称

        2. 操作步骤:
          a) 填写所有必填字段
          b) 点击"开始监听"按钮
          c) 程序将在后台监听指定群聊的消息

        3. 群聊命令:
          /api chat - 切换到DeepSeek API回复模式
          /local chat - 切换到本地AI回复模式
          /help - 显示帮助信息

        4. 使用AI功能:
          在群聊中 @你的昵称 + 问题，AI会自动回复

        5. 停止监听:
          点击"停止监听"按钮可以停止消息监听

        6. 注意事项:
          - 确保微信桌面版已登录并保持运行
          - 本地AI服务需在 http://localhost:5000 运行
          - 使用API模式需要有效的DeepSeek API密钥

        7. 日志功能:
          所有消息和系统事件都会记录在日志区域和日志文件中
        """

        help_text_area = scrolledtext.ScrolledText(help_window, wrap=tk.WORD)
        help_text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        help_text_area.insert(tk.INSERT, help_text)
        help_text_area.configure(state='disabled')

        close_btn = ttk.Button(
            help_window,
            text="关闭",
            command=help_window.destroy
        )
        close_btn.pack(pady=10)

    def log_callback(self, message):
        """日志回调函数"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.update()


if __name__ == "__main__":
    root = tk.Tk()
    app = WeChatListenerUI(root)
    root.mainloop()