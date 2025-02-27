import paramiko
import threading
import time

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
            while self.connected and self.channel:
                if self.channel.recv_ready():
                    data = self.channel.recv(1024)
                    callback(data.decode('utf-8', errors='replace'))
                time.sleep(0.1)
        
        thread = threading.Thread(target=receive_data)
        thread.daemon = True
        thread.start()

    def send_raw(self, command):
        """发送原始命令，包括特殊字符"""
        if self.connected and self.channel:
            try:
                print(f"发送原始命令: {repr(command)}")  # 控制台日志
                # 特殊处理Tab键
                if command == "\t":
                    print("检测到Tab键，发送Tab字符")  # 控制台日志
                    # 尝试使用多种方式发送Tab
                    try:
                        # 方法1: ASCII码9
                        self.channel.send(bytes([9]))
                        print("使用ASCII码9发送Tab成功")
                    except:
                        # 方法2: 尝试直接发送字符串
                        print("方法1失败，尝试方法2")
                        self.channel.send("\t")
                else:
                    # 发送其他命令
                    self.channel.send(command)
            except Exception as e:
                print(f"发送命令错误: {str(e)}")  # 控制台日志 