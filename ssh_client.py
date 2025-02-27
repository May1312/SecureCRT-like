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
                if command == "\t":
                    # 直接发送 Tab ASCII 码
                    self.channel.send(b'\t')
                else:
                    self.channel.send(command)
            except Exception as e:
                print(f"发送命令错误: {str(e)}") 