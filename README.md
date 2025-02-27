# SecureTerminal

SecureTerminal 是一个基于 PyQt6 的 SSH 终端客户端，旨在提供类似 SecureCRT 的功能。它支持会话管理、命令补全、历史记录等特性，帮助用户更高效地管理和使用 SSH 连接。

## 功能特点

### 会话管理
- **保存/加载 SSH 连接配置**：轻松管理多个 SSH 会话。
- **支持密码和密钥文件认证**：提供多种认证方式以确保连接安全。
- **快速连接已保存会话**：通过简单的点击即可快速连接。
- **会话配置本地持久化**：所有配置均保存在本地，方便随时调用。

### 终端功能
- **命令自动补全**：使用 Tab 键快速补全命令。
- **命令历史记录**：通过上下方向键浏览历史命令。
- **ANSI 转义序列支持**：支持丰富的终端显示效果。
- **经典黑底绿字终端样式**：提供经典的终端视觉体验。

### 界面特性
- **多标签页支持**：同时管理多个会话。
- **可分离的会话列表面板**：灵活调整界面布局。
- **右键菜单**：支持复制、粘贴和终止命令等操作。
- **自定义会话名称**：根据需要命名会话，便于识别。

## 安装

### 依赖要求
- Python 3.8+
- PyQt6
- paramiko
- pyqtermwidget

### 安装步骤

1. 克隆仓库
   ```bash
   git clone https://github.com/yourusername/SecureTerminal.git
   cd SecureTerminal
   ```

2. 安装依赖
   ```bash
   pip install PyQt6
   pip install paramiko
   pip install pyqtermwidget
   ```

3. 运行程序
   ```bash
   python main.py
   ```

## 使用说明

### 创建新会话
1. 点击"新建会话"按钮
2. 填写服务器信息：
   - 主机名/IP地址
   - 端口号（默认22）
   - 用户名
   - 认证方式（密码/密钥文件）
3. 点击"保存"并连接

### 快捷键
- `Ctrl+T`: 新建标签页
- `Ctrl+W`: 关闭当前标签页
- `Ctrl+Tab`: 切换标签页
- `Ctrl+C`: 终止当前命令
- `Ctrl+V`: 粘贴
- `Ctrl+Shift+C`: 复制
- `F11`: 全屏模式

## 配置文件

会话配置保存在用户目录下的 `.secureterminal/config.json` 文件中。

## 贡献指南

欢迎提交 Pull Request 和 Issue！在提交代码前，请确保：
1. 代码符合 PEP 8 规范
2. 添加必要的单元测试
3. 更新相关文档

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 致谢

感谢以下开源项目：
- PyQt6
- paramiko
- pyqtermwidget

## 更新日志