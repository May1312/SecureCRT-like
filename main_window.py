from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QLineEdit, QPushButton, QTextEdit, 
                           QTabWidget, QListWidget, QFormLayout, QMessageBox,
                           QSpinBox, QFileDialog, QCheckBox, QSplitter, QApplication)
from PyQt6.QtCore import Qt, QSettings, QEvent, QObject, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QKeyEvent, QTextCursor
import re  # 添加正则表达式支持
import os  # 添加os模块支持
import time  # 添加time模块支持

# 添加缺失的导入
from ssh_client import SSHClient

class GlobalEventFilter(QObject):
    """全局事件过滤器，用于捕获Tab键和Ctrl+C"""
    def __init__(self, terminal_inputs=None):
        super().__init__()
        self.terminal_inputs = terminal_inputs or []  # 存储所有终端输入框的引用
    
    def reset_completion_state(self, input_box, ssh_client):
        """重置补全状态"""
        input_box.tab_completion_active = False
        ssh_client.tab_completion = False
    
    def eventFilter(self, obj, event):
        # 处理按键事件
        if (event.type() == QEvent.Type.KeyPress and 
            isinstance(event, QKeyEvent)):
            
            # 检查是否有活动的终端输入框
            for input_box, terminal_output, ssh_client in self.terminal_inputs:
                if input_box.hasFocus() and ssh_client and ssh_client.connected:
                    # 处理Tab键
                    if event.key() == Qt.Key.Key_Tab:
                        try:
                            # 记录当前命令
                            current_text = input_box.text()
                            if not current_text:
                                return True
                            
                            # 记录原始命令和状态
                            input_box.original_command = current_text
                            input_box.tab_completion_active = True
                            ssh_client.current_command = current_text
                            
                            # 先发送当前命令
                            ssh_client.channel.send(current_text.encode())
                            time.sleep(0.05)
                            
                            # 发送Tab
                            ssh_client.send_raw("\t")
                            
                            # 强制保持焦点
                            input_box.setFocus(Qt.FocusReason.OtherFocusReason)
                            
                            return True
                            
                        except Exception as e:
                            if terminal_output:
                                terminal_output.append(f"\n[错误] Tab发送失败: {str(e)}")
                            # 确保在异常情况下重置状态
                            input_box.tab_completion_active = False
                            ssh_client.tab_completion = False
                            return True
                    
                    # 处理Ctrl+C
                    elif event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        try:
                            ssh_client.channel.send(b'\x03')  # Ctrl+C
                            return True
                        except Exception as e:
                            pass
        
        # 默认处理
        return super().eventFilter(obj, event)

    def register_terminal(self, input_box, terminal_output, ssh_client):
        """注册终端输入框"""
        self.terminal_inputs.append((input_box, terminal_output, ssh_client))
    
    def unregister_terminal(self, input_box):
        """注销终端输入框"""
        self.terminal_inputs = [(i, t, s) for i, t, s in self.terminal_inputs if i != input_box]

class TabCompletionHandler:
    """处理Tab补全功能的辅助类"""
    def __init__(self):
        self.in_completion = False  # 是否正在进行补全
        self.original_command = ""  # 用户原始输入的命令
        self.last_output = ""  # 上次接收到的输出
    
    def start_completion(self, command):
        """开始Tab补全过程"""
        self.in_completion = True
        self.original_command = command
        self.last_output = ""
    
    def process_output(self, output, command_input):
        """处理服务器返回的补全输出"""
        if not self.in_completion:
            return False
        
        # 保存输出以分析
        self.last_output += output
        
        # 尝试找到补全后的命令
        lines = self.last_output.strip().split('\n')
        if not lines:
            return False
        
        # 方法1: 在最后一行查找提示符后的内容
        last_line = lines[-1].strip()
        prompt_match = re.search(r'\[.*?\]\s*[#\$]\s*(.*)', last_line)
        if prompt_match:
            completed_cmd = prompt_match.group(1)
            if completed_cmd and completed_cmd != self.original_command:
                # 找到了补全后的命令，更新输入框
                command_input.setText(completed_cmd)
                command_input.setCursorPosition(len(completed_cmd))
                self.in_completion = False
                return True
        
        # 方法2: 查找唯一匹配项
        for line in lines:
            if line.startswith(self.original_command) and line != self.original_command:
                completed_cmd = line.strip()
                command_input.setText(completed_cmd)
                command_input.setCursorPosition(len(completed_cmd))
                self.in_completion = False
                return True
        
        return False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecureTerminal SSH客户端")
        self.resize(1000, 700)
        
        # 创建全局事件过滤器
        self.event_filter = GlobalEventFilter()
        QApplication.instance().installEventFilter(self.event_filter)
        
        # 创建主分割器
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)
        
        # 创建左侧会话列表
        self.create_session_list()
        
        # 创建右侧内容区域
        self.content_widget = QTabWidget()
        self.content_widget.setTabsClosable(True)
        self.content_widget.tabCloseRequested.connect(self.close_tab)
        self.main_splitter.addWidget(self.content_widget)
        
        # 添加一个默认的连接标签页
        self.add_connection_tab()
        
        # 设置分割比例
        self.main_splitter.setSizes([200, 800])
        
        # 加载保存的连接
        self.load_connections()
        
        # 设置基本样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            
            /* 左侧会话列表样式 */
            QListWidget {
                background-color: #ffffff;
                border: 2px solid #a0a0a0;  /* 更粗更深的边框 */
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                color: #000000;  /* 确保文字为黑色 */
                padding: 8px;    /* 增加内边距 */
                margin: 2px;     /* 增加项目间距 */
                border: 1px solid #d0d0d0;  /* 默认显示边框 */
                border-radius: 3px;
                background: #f8f8f8;  /* 轻微的背景色 */
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #000000;  /* 保持文字黑色 */
                border: 2px solid #1976d2;  /* 更粗的边框 */
                font-weight: bold;  /* 选中项加粗 */
            }
            QListWidget::item:hover {
                background: #f0f0f0;
                border: 1px solid #1976d2;
            }
            
            /* 标签页样式 */
            QTabWidget::pane {
                border: 2px solid #a0a0a0;  /* 更粗更深的边框 */
                background: white;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #e8e8e8;  /* 更深的背景色 */
                border: 2px solid #a0a0a0;  /* 更粗更深的边框 */
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 12px;
                margin-right: 2px;
                color: #000000;  /* 确保文字为黑色 */
            }
            QTabBar::tab:selected {
                background: white;
                border: 2px solid #1976d2;  /* 选中标签使用主题色边框 */
                border-bottom: 2px solid white;  /* 底部边框为白色 */
                font-weight: bold;  /* 选中标签文字加粗 */
            }
            QTabBar::tab:hover:!selected {
                background: #f0f0f0;
                border: 2px solid #b0b0b0;
            }
            
            /* 按钮样式 */
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
            QPushButton:disabled {
                background-color: #bbdefb;
                color: #90caf9;
            }
            
            /* 输入框样式 */
            QLineEdit {
                padding: 5px;
                border: 1px solid #c0c0c0;  /* 加深边框颜色 */
                border-radius: 3px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #1976d2;
            }
            
            /* 终端输入框特殊样式 */
            #terminalInput {
                background-color: #000000;
                color: #00FF00;
                border: none;
            }
            
            /* 标签样式 */
            QLabel {
                color: #424242;
                font-weight: normal;  /* 默认不加粗 */
            }
            
            /* 复选框样式 */
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #c0c0c0;  /* 加深边框颜色 */
                background: white;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #1976d2;
                background: #1976d2;
            }
            
            /* 端口输入框样式 */
            QSpinBox {
                padding: 5px;
                border: 1px solid #c0c0c0;  /* 加深边框颜色 */
                border-radius: 3px;
                background: white;  /* 移除黑色背景 */
                color: black;  /* 确保文字为黑色 */
            }
            QSpinBox:focus {
                border: 1px solid #1976d2;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                border: none;
                background: #f5f5f5;
                border-radius: 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #e3f2fd;
            }
        """)
    
    def create_session_list(self):
        """创建左侧会话列表面板"""
        session_panel = QWidget()
        layout = QVBoxLayout(session_panel)
        
        # 标题
        title_label = QLabel("已保存会话")
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label)
        
        # 会话列表
        self.session_list = QListWidget()
        self.session_list.itemDoubleClicked.connect(self.load_session)
        layout.addWidget(self.session_list)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("新建")
        add_btn.clicked.connect(self.add_connection_tab)
        add_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        connect_btn = QPushButton("连接")
        connect_btn.clicked.connect(self.connect_selected)
        connect_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self.delete_selected)
        delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(connect_btn)
        button_layout.addWidget(delete_btn)
        
        layout.addLayout(button_layout)
        
        # 添加到主分割器
        self.main_splitter.addWidget(session_panel)
    
    def add_connection_tab(self):
        """添加连接配置标签页"""
        connect_tab = QWidget()
        tab_layout = QVBoxLayout(connect_tab)
        
        # 连接表单
        form_layout = QFormLayout()
        
        self.session_name = QLineEdit()
        self.hostname = QLineEdit()
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(22)
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.use_key = QCheckBox("使用密钥文件")
        
        # 密钥文件选择
        key_widget = QWidget()
        key_layout = QHBoxLayout(key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        
        self.key_file = QLineEdit()
        self.key_file.setEnabled(False)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.setEnabled(False)
        browse_btn.clicked.connect(self.browse_key_file)
        
        key_layout.addWidget(self.key_file)
        key_layout.addWidget(browse_btn)
        
        # 添加表单项
        form_layout.addRow("会话名称:", self.session_name)
        form_layout.addRow("主机名/IP:", self.hostname)
        form_layout.addRow("端口:", self.port)
        form_layout.addRow("用户名:", self.username)
        form_layout.addRow("密码:", self.password)
        form_layout.addRow(self.use_key)
        form_layout.addRow("密钥文件:", key_widget)
        
        # 添加到标签页布局
        tab_layout.addLayout(form_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        connect_btn = QPushButton("连接")
        connect_btn.clicked.connect(self.connect_to_server)
        connect_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        save_btn = QPushButton("保存会话")
        save_btn.clicked.connect(self.save_connection)
        save_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        button_layout.addWidget(connect_btn)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        
        tab_layout.addLayout(button_layout)
        tab_layout.addStretch()
        
        # 绑定事件
        self.use_key.toggled.connect(lambda checked: self.toggle_key_auth(checked, self.key_file, browse_btn))
        
        # 添加到标签页容器
        index = self.content_widget.addTab(connect_tab, "新建连接")
        self.content_widget.setCurrentIndex(index)
    
    def toggle_key_auth(self, checked, key_file, browse_btn):
        """切换密钥认证"""
        key_file.setEnabled(checked)
        browse_btn.setEnabled(checked)
        self.password.setEnabled(not checked)
    
    def browse_key_file(self):
        """浏览密钥文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择SSH密钥文件")
        if file_path:
            self.key_file.setText(file_path)
    
    def connect_to_server(self):
        """连接到SSH服务器并创建终端窗口"""
        host = self.hostname.text()
        port = self.port.value()
        username = self.username.text()
        
        if not host or not username:
            QMessageBox.warning(self, "输入错误", "请输入主机名和用户名")
            return
        
        # 创建终端标签页
        terminal_tab = QWidget()
        terminal_tab.setStyleSheet("background-color: #000000;")  # 设置整个标签页为黑色背景
        terminal_layout = QVBoxLayout(terminal_tab)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(0)  # 减少间距，更像传统终端
        
        # 终端输出区域
        terminal_output = QTextEdit()
        terminal_output.setReadOnly(True)
        terminal_output.setAcceptRichText(False)
        terminal_output.setFont(QFont("Courier New", 10))
        terminal_output.setStyleSheet("background-color: #000000; color: #00FF00; border: none;")
        
        # 创建SSH客户端
        ssh_client = SSHClient()
        
        # 添加右键菜单
        terminal_output.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        def show_context_menu(pos):
            menu = terminal_output.createStandardContextMenu()
            menu.addSeparator()
            
            # 添加终止命令选项
            terminate_action = menu.addAction("终止命令 (Ctrl+C)")
            terminate_action.triggered.connect(lambda: ssh_client.send_raw("\x03"))
            
            # 添加中断选项
            interrupt_action = menu.addAction("中断 (Ctrl+Z)")
            interrupt_action.triggered.connect(lambda: ssh_client.send_raw("\x1A"))
            
            menu.exec(terminal_output.mapToGlobal(pos))
        
        terminal_output.customContextMenuRequested.connect(show_context_menu)
        
        # 创建命令输入区域
        input_widget = QWidget()
        input_widget.setStyleSheet("background-color: #000000;")
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(0)
        
        # 定义current_path作为非局部变量
        current_path = "~"
        
        # 设置提示符
        prompt_label = QLabel(f"[{username}@{host} {current_path}]# ")
        prompt_label.setStyleSheet("color: #00FF00; font-family: 'Courier New'; background-color: #000000;")
        
        # 命令输入框
        command_input = TerminalInput(ssh_client, terminal_output)

        # 命令历史功能
        command_history = []
        history_index = -1
        
        input_layout.addWidget(prompt_label)
        input_layout.addWidget(command_input, 1)
        
        # 然后添加输入小部件到终端布局
        terminal_layout.addWidget(terminal_output, 1)
        terminal_layout.addWidget(input_widget, 0)
        
        # 修改终端输出处理函数
        def update_terminal(data):
            try:
                # 处理ANSI转义序列和控制字符
                clean_data = data
                
                # 转义序列处理
                clean_data = re.sub(r'\x1b\[\d+(?:;\d+)*[mK]', '', clean_data)
                clean_data = re.sub(r'\x1b\[\d*[ABCDEFGHJKST]', '', clean_data)
                
                # 控制字符处理
                control_chars = ['\x07', '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', 
                                '\x11', '\x12', '\x13', '\x14', '\x15', '\x16', '\x17', 
                                '\x18', '\x19', '\x1a', '\x1c', '\x1d', '\x1e', '\x1f']
                for char in control_chars:
                    clean_data = clean_data.replace(char, '')
                
                # 换行符处理
                clean_data = clean_data.replace('\r\n', '\n')
                clean_data = clean_data.replace('\r', '\n')
                
                # 其他特殊序列
                clean_data = re.sub(r'\x1b\][^\a]*(?:\a|\x1b\\)', '', clean_data)
                
                # 限制历史大小
                current_text = terminal_output.toPlainText()
                if len(current_text) > 100000:
                    terminal_output.setPlainText(current_text[-50000:])
                
                # 添加输出到终端
                if clean_data.strip():
                    terminal_output.append(clean_data.strip())
                    
                    # 输出补全状态用于调试
                    if command_input.tab_completion_active:
                        terminal_output.append(f"\n[调试] 处理补全响应，原始命令: {command_input.original_command}")
                
                # 检查Tab补全结果
                if command_input.tab_completion_active:
                    try:
                        # 分析输出内容
                        lines = clean_data.strip().split('\n')
                        
                        # 过滤并处理补全选项
                        completion_lines = []
                        current_cmd = command_input.original_command.strip()
                        
                        # 处理每一行
                        for line in lines:
                            line = line.strip()
                            # 跳过空行和提示符行
                            if not line or line == current_cmd:
                                continue
                            
                            # 处理可能包含多个选项的行
                            words = line.split()
                            for word in words:
                                word = word.strip()
                                if word and word.startswith(current_cmd):
                                    completion_lines.append(word)
                        
                        # 去重并排序
                        completion_lines = sorted(set(completion_lines))
                        
                        if completion_lines:
                            # 如果只有一个选项，直接补全
                            if len(completion_lines) == 1:
                                new_text = completion_lines[0]
                                if new_text != current_cmd:
                                    command_input.setText(new_text)
                                    command_input.setCursorPosition(len(new_text))
                            else:
                                # 找到共同前缀
                                common = os.path.commonprefix(completion_lines)
                                if common and len(common) > len(current_cmd):
                                    command_input.setText(common)
                                    command_input.setCursorPosition(len(common))
                                
                                # 显示所有可能的补全选项
                                terminal_output.append("\n可能的补全选项:")
                                for option in completion_lines:
                                    terminal_output.append(option)
                        
                        # 重置补全状态的条件：
                        # 1. 找到并应用了补全选项
                        # 2. 收到了提示符
                        # 3. 没有找到任何补全选项
                        if completion_lines or ']#' in clean_data or '$' in clean_data or not lines:
                            command_input.tab_completion_active = False
                            ssh_client.tab_completion = False
                        
                    except Exception as e:
                        terminal_output.append(f"\n[错误] 补全处理失败: {str(e)}")
                        command_input.tab_completion_active = False
                        ssh_client.tab_completion = False
                
                # 确保滚动到底部
                QApplication.processEvents()
                terminal_output.ensureCursorVisible()
                cursor = terminal_output.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                terminal_output.setTextCursor(cursor)
                scrollbar = terminal_output.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
                
                # 更新路径信息
                path_match = re.search(r'\[.*?@.*? (.*?)\]', clean_data)
                if path_match:
                    current_path = path_match.group(1)
                    prompt_label.setText(f"[{username}@{host} {current_path}]# ")
            
            except Exception as e:
                # 出错时显示原始数据
                terminal_output.append(data)
                # 确保滚动到底部
                scrollbar = terminal_output.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        
        # 连接服务器
        success = False
        if self.use_key.isChecked():
            key_file = self.key_file.text()
            success, message = ssh_client.connect(host, port, username, key_file=key_file)
        else:
            password = self.password.text()
            success, message = ssh_client.connect(host, port, username, password=password)
        
        if success:
            # 启动接收数据
            ssh_client.start_receiving(update_terminal)
            
            # 初始欢迎信息
            update_terminal(f"连接到 {username}@{host}:{port}\n")
            
            # 注册到全局事件过滤器 - 确保使用正确的参数
            self.event_filter.register_terminal(command_input, terminal_output, ssh_client)
            
            # 打印确认信息
            terminal_output.append("\n按Tab键可以进行命令补全")
            
            # 清理函数
            def cleanup_terminal():
                self.event_filter.unregister_terminal(command_input)
                ssh_client.disconnect()
            
            terminal_tab.destroyed.connect(cleanup_terminal)
            
            # 发送命令功能
            def send_command():
                cmd = command_input.text()
                if cmd:
                    # 添加到历史
                    command_history.insert(0, cmd)
                    if len(command_history) > 100:
                        command_history.pop()
                    command_input.history_index = -1
                    
                    # 显示命令
                    terminal_output.append(f"{prompt_label.text()} {cmd}")
                    
                    # 发送命令
                    ssh_client.send_command(cmd)
                    command_input.clear()
            
            command_input.returnPressed.connect(send_command)
            
            # 添加标签页
            tab_name = self.session_name.text() or f"{username}@{host}"
            index = self.content_widget.addTab(terminal_tab, tab_name)
            self.content_widget.setCurrentIndex(index)
            
            # 设置焦点
            command_input.setFocus()
            
            # 保存SSH客户端实例
            terminal_tab.ssh_client = ssh_client
        else:
            QMessageBox.critical(self, "连接失败", message)
    
    def save_connection(self):
        """保存连接配置"""
        name = self.session_name.text()
        if not name:
            QMessageBox.warning(self, "输入错误", "请输入会话名称")
            return
        
        host = self.hostname.text()
        if not host:
            QMessageBox.warning(self, "输入错误", "请输入主机名")
            return
        
        # 保存到设置
        settings = QSettings("SSH客户端", "连接")
        settings.beginGroup(name)
        settings.setValue("hostname", host)
        settings.setValue("port", self.port.value())
        settings.setValue("username", self.username.text())
        settings.setValue("use_key", self.use_key.isChecked())
        
        if not self.use_key.isChecked():
            settings.setValue("password", self.password.text())
        else:
            settings.setValue("key_file", self.key_file.text())
        
        settings.endGroup()
        
        # 添加到会话列表
        items = self.session_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if not items:
            self.session_list.addItem(name)
        
        QMessageBox.information(self, "保存成功", f"会话 '{name}' 已保存")
    
    def load_connections(self):
        """加载保存的连接"""
        settings = QSettings("SSH客户端", "连接")
        groups = settings.childGroups()
        
        for name in groups:
            self.session_list.addItem(name)
    
    def load_session(self, item):
        """加载选中的会话"""
        name = item.text()
        
        settings = QSettings("SSH客户端", "连接")
        settings.beginGroup(name)
        
        # 添加连接标签页
        self.add_connection_tab()
        
        # 填充信息
        self.session_name.setText(name)
        self.hostname.setText(settings.value("hostname", ""))
        self.port.setValue(int(settings.value("port", 22)))
        self.username.setText(settings.value("username", ""))
        
        use_key = settings.value("use_key", "false") == "true"
        self.use_key.setChecked(use_key)
        
        if use_key:
            self.key_file.setText(settings.value("key_file", ""))
            self.key_file.setEnabled(True)
            
            # 查找浏览按钮并启用
            for child in self.content_widget.currentWidget().findChildren(QPushButton):
                if child.text() == "浏览...":
                    child.setEnabled(True)
                    break
        else:
            self.password.setText(settings.value("password", ""))
        
        settings.endGroup()
    
    def connect_selected(self):
        """连接选中的会话"""
        if self.session_list.currentItem():
            name = self.session_list.currentItem().text()
            
            settings = QSettings("SSH客户端", "连接")
            settings.beginGroup(name)
            
            # 填充连接信息到当前标签页
            self.session_name.setText(name)
            self.hostname.setText(settings.value("hostname", ""))
            self.port.setValue(int(settings.value("port", 22)))
            self.username.setText(settings.value("username", ""))
            
            use_key = settings.value("use_key", "false") == "true"
            self.use_key.setChecked(use_key)
            
            if use_key:
                self.key_file.setText(settings.value("key_file", ""))
                self.key_file.setEnabled(True)
                
                # 查找浏览按钮并启用
                for child in self.content_widget.currentWidget().findChildren(QPushButton):
                    if child.text() == "浏览...":
                        child.setEnabled(True)
                        break
            else:
                self.password.setText(settings.value("password", ""))
            
            settings.endGroup()
            
            # 直接连接服务器
            self.connect_to_server()
    
    def delete_selected(self):
        """删除选中的会话"""
        current = self.session_list.currentItem()
        if current:
            name = current.text()
            
            reply = QMessageBox.question(self, "确认删除", 
                                       f"确定要删除会话 '{name}' 吗?", 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                # 从设置中删除
                settings = QSettings("SSH客户端", "连接")
                settings.remove(name)
                
                # 从列表中删除
                self.session_list.takeItem(self.session_list.row(current))
    
    def close_tab(self, index):
        """关闭标签页"""
        # 获取标签页
        tab = self.content_widget.widget(index)
        
        # 关闭标签页
        self.content_widget.removeTab(index)

# 完全覆盖输入框的键盘事件处理
class TerminalInput(QLineEdit):
    def __init__(self, ssh_client, terminal_output=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("terminalInput")
        self.ssh_client = ssh_client
        self.terminal_output = terminal_output
        self.command_history = []
        self.history_index = -1
        self.setFont(QFont("Courier New", 10))
        self.setStyleSheet("background-color: #000000; color: #00FF00; border: none;")
        self.tab_completion_active = False
        self.original_command = ""
        
        # 设置焦点策略
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def keyPressEvent(self, event):
        # 只处理上下箭头历史命令
        if event.key() == Qt.Key.Key_Up:
            if self.command_history and self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.setText(self.command_history[self.history_index])
                self.setCursorPosition(len(self.text()))
            return
        
        elif event.key() == Qt.Key.Key_Down:
            if self.history_index > 0:
                self.history_index -= 1
                self.setText(self.command_history[self.history_index])
            elif self.history_index == 0:
                self.history_index = -1
                self.clear()
            return
            
        # 其他键的默认处理
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # 如果是在 Tab 补全过程中，阻止失焦
        if self.tab_completion_active:
            QTimer.singleShot(1, lambda: self.setFocus(Qt.FocusReason.MouseFocusReason))
            event.ignore()
            return
        
        super().focusOutEvent(event)

# 激活Tab处理
# setup_tab_handling() 