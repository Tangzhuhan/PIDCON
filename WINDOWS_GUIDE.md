# Windows平台代码修改指南

## Python 3.7.9 环境配置
如果使用 Python 3.7.9，需要特别注意以下事项：

1. 安装依赖包时指定兼容版本：
```bash
pip install PyQt5==5.15.4
pip install pyqtgraph==0.12.3
pip install pyserial==3.5
pip install pandas==1.3.5
pip install appdirs==1.4.4
```

2. 代码兼容性检查：
   - 确保没有使用 Python 3.8+ 特有的语法
   - 检查 f-strings 的使用（Python 3.7 支持）
   - 检查 dataclasses 的使用（需要额外安装）
   - 检查 typing 的使用（需要额外安装）

3. 打包注意事项：
   - 使用 PyInstaller 3.6 或更高版本
   - 确保所有依赖包都兼容 Python 3.7.9
   - 测试打包后的程序在 Windows 7/10 上的兼容性

## 1. 路径处理（必须修改）
在Windows平台上，所有文件路径必须使用以下方式处理：

1. 导入必要的模块：
```python
import os
import sys
from appdirs import user_data_dir
```

2. 获取用户数据目录：
```python
# 获取用户数据目录
data_dir = user_data_dir('PIDTempControl', 'Personal')
os.makedirs(data_dir, exist_ok=True)
```

3. 构建文件路径：
```python
# 错误示例（不要这样写）：
file_path = "C:/Users/username/Documents/data.csv"
config_path = "\\Program Files\\PID Control\\config.json"

# 正确示例（必须这样写）：
file_path = os.path.join(data_dir, 'data.csv')
config_path = os.path.join(data_dir, 'config.json')
```

4. 处理资源文件路径：
```python
# 错误示例（不要这样写）：
icon_path = "icon.ico"

# 正确示例（必须这样写）：
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(base_path, 'icon.ico')
```

## 2. 串口处理（必须修改）
在Windows平台上，串口处理必须使用以下方式：

1. 导入必要的模块：
```python
import serial
import platform
import serial.tools.list_ports
```

2. 获取可用串口列表：
```python
# 错误示例（不要这样写）：
if platform.system() == 'Windows':
    ports = [f'COM{i}' for i in range(1, 10)]

# 正确示例（必须这样写）：
def get_available_ports():
    ports = []
    try:
        if platform.system() == 'Windows':
            for i in range(1, 10):
                try:
                    port = f'COM{i}'
                    ser = serial.Serial(port)
                    ser.close()
                    ports.append(port)
                except serial.SerialException:
                    continue
    except Exception as e:
        print(f"获取串口列表时出错: {e}")
    return ports
```

3. 连接串口：
```python
# 错误示例（不要这样写）：
ser = serial.Serial('COM1', 9600)

# 正确示例（必须这样写）：
def connect_serial(port, baudrate=9600):
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=1,
            write_timeout=1
        )
        if ser.is_open:
            print(f"成功连接到串口 {port}")
            return ser
        return None
    except Exception as e:
        print(f"连接串口时出错: {e}")
        return None
```

4. 读取串口数据：
```python
# 错误示例（不要这样写）：
def read_serial(ser):
    return ser.readline()

# 正确示例（必须这样写）：
def read_serial(ser, timeout=1.0):
    try:
        if not ser or not ser.is_open:
            return None
        ser.timeout = timeout
        data = ser.readline()
        if data:
            return data.decode('utf-8').strip()
        return None
    except Exception as e:
        print(f"读取串口数据时出错: {e}")
        return None
```

5. 关闭串口：
```python
# 错误示例（不要这样写）：
ser.close()

# 正确示例（必须这样写）：
def close_serial(ser):
    try:
        if ser and ser.is_open:
            ser.close()
            print("串口已关闭")
    except Exception as e:
        print(f"关闭串口时出错: {e}")
```

## 3. 代码修改检查清单
在打包前，请确保完成以下检查：

1. 路径处理检查：
   - [ ] 所有文件路径都使用 `os.path.join()`
   - [ ] 没有硬编码的路径分隔符
   - [ ] 使用 `user_data_dir` 获取配置目录
   - [ ] 使用 `os.path.expanduser("~")` 获取用户主目录

2. 串口处理检查：
   - [ ] 串口检测代码兼容 Windows 格式
   - [ ] 所有串口操作都有错误处理
   - [ ] 串口通信有超时设置
   - [ ] 串口关闭有错误处理

3. 配置文件检查：
   - [ ] 配置文件路径使用正确的方式构建
   - [ ] 确保有写入权限
   - [ ] 配置文件备份机制

4. 资源文件检查：
   - [ ] 图标文件路径正确
   - [ ] 其他资源文件路径正确
   - [ ] 打包时包含所有必要资源

## 4. 常见问题解决
1. 路径问题：
   - 问题：程序找不到配置文件
   - 解决：检查路径构建方式，确保使用 `os.path.join()`

2. 串口问题：
   - 问题：无法识别串口
   - 解决：检查串口检测代码，确保正确处理 Windows 格式

3. 权限问题：
   - 问题：无法写入文件
   - 解决：检查目录权限，确保使用正确的用户目录

4. 打包问题：
   - 问题：打包后找不到资源文件
   - 解决：检查资源文件路径处理，确保使用 `sys._MEIPASS` 