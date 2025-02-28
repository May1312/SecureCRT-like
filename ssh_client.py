import paramiko
import threading
import time
import re

class SSHClient:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.channel = None
        self.connected = False
        self.tab_completion = False  # 标记是否正在进行Tab补全
        self.current_command = ""    # 当前命令
        
    def connect(self, hostname, port, username, password=None, key_file=None):
        """建立SSH连接"""
        try:
            if key_file:
                self.client.connect(hostname, port=port, username=username, key_filename=key_file)
            else:
                self.client.connect(hostname, port=port, username=username, password=password)
                
            self.channel = self.client.invoke_shell()
            self.connected = True
            return True, "连接成功"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def disconnect(self):
        """断开SSH连接"""
        if self.connected:
            self.channel.close()
            self.client.close()
            self.connected = False
    
    def send_command(self, command):
        """发送命令到SSH服务器"""
        if self.connected and self.channel:
            self.channel.send(command + '\n')
    
    def start_receiving(self, callback):
        """启动接收数据的线程"""
        def receive_data():
            buffer = ""
            last_data_time = 0
            while self.connected and self.channel:
                if self.channel.recv_ready():
                    try:
                        # 接收数据
                        data = self.channel.recv(1024).decode('utf-8', errors='replace')
                        last_data_time = time.time()
                        
                        # 处理数据中的特殊字符
                        data = data.replace('\x07', '')  # 删除响铃
                        data = data.replace('\x1b[K', '') # 删除清除行
                        data = re.sub(r'\x1b\[\d*[A-Za-z]', '', data)  # 删除ANSI转义序列
                        
                        # 缓冲数据
                        buffer += data
                        
                        # 如果有完整的行或提示符，处理数据
                        if '\n' in buffer or ']#' in buffer or '$' in buffer:
                            if buffer.strip():
                                callback(buffer)
                            buffer = ""
                            
                    except Exception as e:
                        print(f"接收数据错误: {str(e)}")
                        buffer = ""
                else:
                    # 如果超过100ms没有新数据，且有未处理的数据，则处理它
                    if buffer and time.time() - last_data_time > 0.1:
                        if buffer.strip():
                            callback(buffer)
                        buffer = ""
                    time.sleep(0.01)
            
            # 处理剩余的缓冲数据
            if buffer:
                callback(buffer)
        
        thread = threading.Thread(target=receive_data)
        thread.daemon = True
        thread.start()

    def send_raw(self, command):
        """发送原始命令，包括特殊字符"""
        if self.connected and self.channel:
            try:
                if command == "\t":
                    # 发送Tab字符
                    self.channel.send(b'\t')
                    time.sleep(0.1)  # 等待响应
                else:
                    self.channel.send(command)
                    self.tab_completion = False  # 非Tab键时重置补全状态
            except Exception as e:
                print(f"发送命令错误: {str(e)}")
                self.tab_completion = False 