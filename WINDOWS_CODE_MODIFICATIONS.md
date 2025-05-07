# Windows平台代码修改指南

## 1. 必须修改的代码位置

### 1.1 路径处理修改
1. 在 `main.py` 中修改配置文件路径（约第50-60行）：
```python
# 原代码：
self.config_dir = "config"
self.config_file = "config/material_params.json"

# 修改为：
import os
from appdirs import user_data_dir
self.config_dir = user_data_dir('PIDTempControl', 'Personal')
os.makedirs(self.config_dir, exist_ok=True)
self.config_file = os.path.join(self.config_dir, 'material_params.json')
```

2. 在 `main.py` 中修改数据保存路径（约第200-210行）：
```python
# 原代码：
save_dir = "data"

# 修改为：
save_dir = os.path.join(os.path.expanduser("~"), "Documents", "PID Data")
os.makedirs(save_dir, exist_ok=True)
```

3. 在 `main.py` 的 `PIDSystemUI` 类的 `__init__` 方法中添加图标设置（约第217-230行）：
```python
# 在 super().__init__() 之后添加：
if getattr(sys, 'frozen', False):
    # 打包后的路径
    base_path = sys._MEIPASS
else:
    # 开发环境的路径
    base_path = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(base_path, 'icon.ico')
if os.path.exists(icon_path):
    self.setWindowIcon(QIcon(icon_path))
```

### 1.2 串口处理修改
1. 在 `main.py` 中修改串口检测代码（约第150-160行）：
```python
# 原代码：
def get_available_ports():
    if platform.system() == 'Windows':
        ports = [f'COM{i}' for i in range(1, 10)]
    else:
        ports = [port.device for port in serial.tools.list_ports.comports()]
    return ports

# 修改为：
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
        else:
            for port in serial.tools.list_ports.comports():
                try:
                    ser = serial.Serial(port.device)
                    ser.close()
                    ports.append(port.device)
                except serial.SerialException:
                    continue
    except Exception as e:
        print(f"获取串口列表时出错: {e}")
    return ports
```

2. 在 `main.py` 中修改串口连接代码（约第400-410行）：
```python
# 原代码：
ser = serial.Serial(port, baudrate)

# 修改为：
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

3. 在 `MOD_700.py` 中修改串口读取代码（约第100-110行）：
```python
# 原代码：
def read_temperature(self, channel):
    return self.ser.readline()

# 修改为：
def read_temperature(self, channel, timeout=1.0):
    try:
        if not self.ser or not self.ser.is_open:
            return None
        self.ser.timeout = timeout
        data = self.ser.readline()
        if data:
            return data.decode('utf-8').strip()
        return None
    except Exception as e:
        print(f"读取温度数据时出错: {e}")
        return None
```

### 1.3 电压限制修改
1. 在 `main.py` 的 `PIDSystemUI` 类的 `add_left_panel_components` 方法中添加电压限制设置（约第306-350行）：
```python
# 在控制参数设置部分添加：
# 最大电压限制设置
self.max_voltage_label = QLabel("Maximum Voltage (V):")
self.left_layout.addWidget(self.max_voltage_label)
self.max_voltage_input = QLineEdit()
self.max_voltage_input.setText("30.0")  # 默认30V
self.left_layout.addWidget(self.max_voltage_input)
```

2. 在 `main.py` 的 `start_control` 方法中添加电压限制设置（约第636-700行）：
```python
# 在获取其他参数的部分添加：
try:
    max_voltage = float(self.max_voltage_input.text())
    if max_voltage <= 0:
        QMessageBox.warning(self, "警告", "最大电压必须大于0")
        return
except ValueError:
    QMessageBox.warning(self, "警告", "最大电压必须是有效的数字")
    return

# 设置PID控制器的最大电压限制
self.pid_controller.set_max_voltage(max_voltage)
```

3. 在 `center_control.py` 的 `PIDController` 类中添加最大电压限制相关代码：
```python
def __init__(self):
    super().__init__()
    self.max_voltage = 30.0  # 默认最大电压限制
    # ... 其他初始化代码 ...

def set_max_voltage(self, max_voltage):
    """设置最大电压限制"""
    self.max_voltage = max_voltage
```

### 1.4 PID输出限制修改
1. 在 `center_control.py` 的 `PIDController` 类的 `update` 方法中修改PID输出限制（约第435-436行）：
```python
# 原代码：
pid_output = max(1.0, min(7.0, pid_output))
print(f"限制后的PID输出: {pid_output}V")

# 修改为：
pid_output = max(1.0, min(self.max_voltage, pid_output))
print(f"限制后的PID输出: {pid_output}V")
```

## 2. 可选修改项

### 2.1 错误处理增强
在 `main.py` 文件开头添加：
```python
import traceback
import sys

def exception_hook(exctype, value, traceback_obj):
    print("未捕获的异常:")
    print("类型:", exctype)
    print("值:", value)
    print("追踪:", traceback.format_tb(traceback_obj))
    sys.__excepthook__(exctype, value, traceback_obj)

sys.excepthook = exception_hook
```

### 2.2 日志记录增强
在 `main.py` 文件开头添加：
```python
import logging
import os
from appdirs import user_data_dir

# 设置日志目录
log_dir = os.path.join(user_data_dir('PIDTempControl', 'Personal'), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 配置日志
logging.basicConfig(
    filename=os.path.join(log_dir, 'pid_control.log'),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

## 3. 打包前检查清单

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

4. 图标文件检查：
   - [ ] 准备一个 `icon.ico` 文件（建议尺寸：256x256像素）
   - [ ] 将图标文件放在项目根目录
   - [ ] 确保图标文件格式正确（必须是 .ico 格式）

5. 电压限制检查：
   - [ ] 最大电压输入框已添加到界面
   - [ ] 最大电压值已正确传递给PID控制器
   - [ ] PID输出限制已正确使用最大电压值
   - [ ] 确保最小电压限制（1.0V）仍然有效
   - [ ] 输入验证和错误处理已实现

## 4. 打包步骤

1. 安装必要的包：
```bash
pip install PyQt5==5.15.4
pip install pyqtgraph==0.12.3
pip install pyserial==3.5
pip install pandas==1.3.5
pip install appdirs==1.4.4
pip install pyinstaller==4.10
```

2. 创建打包配置文件：
```bash
pyinstaller --name=pid_control --windowed --onefile --add-data "icon.ico;." main.py
```

3. 执行打包：
```bash
pyinstaller pid_control.spec
```

4. 测试打包后的程序：
   - 在干净的 Windows 系统上测试
   - 测试所有功能
   - 检查日志文件
   - 验证数据保存功能
   - 验证程序图标是否正确显示

## 5. 常见问题解决

1. 如果程序无法启动：
   - 检查是否所有依赖都已正确安装
   - 检查是否有正确的权限
   - 检查日志文件中的错误信息

2. 如果串口无法识别：
   - 检查设备管理器中的串口设置
   - 确保有正确的驱动程序
   - 检查权限设置

3. 如果数据保存失败：
   - 检查保存目录的写入权限
   - 检查磁盘空间
   - 检查文件是否被其他程序占用

4. 如果程序图标不显示：
   - 检查图标文件格式是否正确（必须是 .ico 格式）
   - 检查图标文件是否在正确的位置
   - 检查打包命令是否正确包含图标文件
   - 检查图标文件路径处理代码是否正确

5. 如果电压限制不起作用：
   - 检查最大电压值是否正确传递到PID控制器
   - 验证PID输出是否在1.0V和最大电压值之间
   - 检查控制台输出的PID输出值是否符合预期
   - 检查日志文件中的相关错误信息 