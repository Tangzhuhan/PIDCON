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
1. 在 `main.py` 的 `get_available_ports` 方法中修改串口获取逻辑（约第200-250行）：
```python
def get_available_ports(self):
    """获取可用的串口列表"""
    ports = []
    if platform.system() == 'Windows':
        # Windows系统
        for i in range(1, 10):
            ports.append(f'COM{i}')
    else:
        # Mac/Linux系统
        for port in serial.tools.list_ports.comports():
            ports.append(port.device)
    return ports
```

2. 在 `main.py` 的 `add_right_panel_components` 方法中修改串口选择相关代码（约第400-450行）：
```python
# 温度传感器串口选择
self.temp_sensor_port_label = QLabel("Temperature Sensor Port:")
self.right_layout.addWidget(self.temp_sensor_port_label)
self.temp_sensor_port_combo = QComboBox()
self.temp_sensor_port_combo.addItems(self.get_available_ports())
# 添加刷新按钮
refresh_ports_button = QPushButton("刷新串口列表")
refresh_ports_button.clicked.connect(self.refresh_ports)
self.right_layout.addWidget(self.temp_sensor_port_combo)
self.right_layout.addWidget(refresh_ports_button)

# 电源发生器串口选择
self.power_supply_port_label = QLabel("Power Supply Port:")
self.right_layout.addWidget(self.power_supply_port_label)
self.power_supply_port_combo = QComboBox()
self.power_supply_port_combo.addItems(self.get_available_ports())
self.right_layout.addWidget(self.power_supply_port_combo)
```

3. 在 `main.py` 中添加刷新串口列表的方法：
```python
def refresh_ports(self):
    """刷新串口列表"""
    # 保存当前选择的串口
    current_temp_port = self.temp_sensor_port_combo.currentText()
    current_power_port = self.power_supply_port_combo.currentText()
    
    # 获取新的串口列表
    ports = self.get_available_ports()
    
    # 更新下拉框
    self.temp_sensor_port_combo.clear()
    self.power_supply_port_combo.clear()
    
    # 添加新的串口列表
    self.temp_sensor_port_combo.addItems(ports)
    self.power_supply_port_combo.addItems(ports)
    
    # 尝试恢复之前的选择
    if current_temp_port in ports:
        self.temp_sensor_port_combo.setCurrentText(current_temp_port)
    if current_power_port in ports:
        self.power_supply_port_combo.setCurrentText(current_power_port)
```

4. 在 `main.py` 的 `start_control` 方法中修改串口连接相关代码（约第636-700行）：
```python
# 连接温度传感器
temp_sensor_port = self.temp_sensor_port_combo.currentText().split(' - ')[0]  # 只取 COM 部分
if not self.pid_controller.connect_sensor(temp_sensor_port):
    QMessageBox.warning(self, "警告", "连接温度传感器失败")
    return
    
# 连接电源发生器
try:
    power_supply_port = self.power_supply_port_combo.currentText().split(' - ')[0]  # 只取 COM 部分
    if not self.pid_controller.connect_power_supply(power_supply_port):
        QMessageBox.warning(self, "警告", "连接电源发生器失败")
        return
except Exception as e:
    QMessageBox.warning(self, "错误", f"连接电源发生器时出错: {str(e)}")
    return
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

7. 串口功能检查：
   - [ ] 串口列表能正确显示所有可用串口
   - [ ] 串口描述信息显示正确
   - [ ] 刷新串口列表功能正常
   - [ ] 串口选择后能正确连接设备
   - [ ] 串口断开后能正确提示错误
   - [ ] 串口重连功能正常

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

7. 如果串口功能异常：
   - 检查设备管理器中串口是否正常显示
   - 检查串口驱动是否正确安装
   - 检查串口是否被其他程序占用
   - 尝试重新插拔设备
   - 检查串口权限设置
   - 检查串口波特率等参数设置

## 2024-03-21: 预热时间设置功能更新

### 修改内容
1. 在左侧面板添加预热时间设置输入框
2. 更新PID控制器预热时间参数设置
3. 修改默认预热时间为20秒

### 具体修改
1. 在 `add_left_panel_components` 方法中添加预热时间设置：
```python
# 预热时间设置
self.warmup_label = QLabel("Warm-up Time (s):")
self.left_layout.addWidget(self.warmup_label)
self.warmup_input = QLineEdit()
self.warmup_input.setText("20")  # 默认20秒
self.left_layout.addWidget(self.warmup_input)
```

2. 在 `start_control` 方法中添加预热时间参数获取和设置：
```python
# 获取预热时间
warmup_time = float(self.warmup_input.text())

# 设置预热时间
self.pid_controller.set_warmup_time(warmup_time)
```

### 注意事项
1. 确保PID控制器类中已实现 `set_warmup_time` 方法
2. 预热时间输入框的值需要做有效性验证
3. 建议添加预热时间的范围限制（例如：5-300秒）

### 测试要点
1. 验证预热时间设置是否正确保存和读取
2. 测试不同预热时间值的效果
3. 验证预热时间参数在控制过程中的正确应用
```

## 6. 数据结构改进

### 改动内容：
```python
# 原来只有一个control_data
self.control_data = {
    'time': [],
    'temperatures': {},
    'voltage': [],
    'current': []
}

# 新增两个数据结构
self.continuous_data = {
    'experiments': [],  # 存储每次实验的数据
    'experiment_count': 0
}

self.current_experiment_data = {
    'time': [],
    'temperatures': {},
    'voltage': [],
    'current': [],
    'start_time': None,
    'end_time': None
}
```

### 改动依据和思路：
- **问题分析**：原来的代码只有一个`control_data`，无法区分单次实验和连续实验的数据
- **解决思路**：采用三级数据结构
  1. `control_data`：用于实时图表显示（不变）
  2. `current_experiment_data`：存储当前单次实验的完整数据
  3. `continuous_data`：存储所有实验的历史数据，支持连续导出

## 7. 数据同步机制优化

### 改动内容：
在`update_plots`方法中，同时更新三个数据结构：
```python
# 同步更新三个数据结构
self.control_data['time'].append(current_time)
self.current_experiment_data['time'].append(current_time)

# 对于每个数据类型都做同样处理
if current_voltage is not None:
    self.control_data['voltage'].append(current_voltage)
    self.current_experiment_data['voltage'].append(current_voltage)
else:
    # 失败时用None填充，保持数据长度一致
    self.control_data['voltage'].append(None)
    self.current_experiment_data['voltage'].append(None)
```

### 改动依据和思路：
- **问题分析**：数据缺失可能是因为：
  1. 不同传感器读取时机不同步
  2. 某个传感器读取失败时没有占位符
  3. 数组长度不一致导致pandas创建DataFrame时出错
- **解决思路**：
  1. 确保所有数据数组长度始终保持一致
  2. 读取失败时用None占位，而不是跳过
  3. 在每次数据更新时同步更新所有相关数据结构

## 8. 导出功能拆分

### 改动内容：
```python
# 原来只有一个导出按钮
self.export_button = QPushButton("Export Data")

# 改为两个按钮
self.export_single_button = QPushButton("Export Current Experiment")
self.export_continuous_button = QPushButton("Export All Experiments")
```

### 改动依据和思路：
- **用户需求**：需要两种导出模式
  1. 单次实验：只导出当前实验数据
  2. 连续实验：导出所有实验数据并自动拼接
- **设计思路**：
  1. 保持界面简洁，用两个按钮明确区分功能
  2. 单次导出使用`current_experiment_data`
  3. 连续导出使用`continuous_data`，包含实验ID和时间信息

## 9. 异常处理改进

### 改动内容：
```python
# 每个传感器读取都有独立的异常处理
for sensor in self.selected_sensors:
    try:
        temp = self.pid_controller.modbus_sensor.read_temperature(sensor)
        # 处理成功的情况
    except Exception as e:
        print(f"读取传感器 {sensor} 温度失败: {e}")
        # 用None填充，保持数据完整性
        channel_key = f'channel_{sensor}'
        if channel_key not in self.control_data['temperatures']:
            self.control_data['temperatures'][channel_key] = [None] * data_length
```

### 改动依据和思路：
- **问题分析**：任何一个传感器读取失败都可能导致整个数据结构不完整
- **解决思路**：
  1. 为每个传感器单独处理异常
  2. 失败时用None填充，确保数据结构完整性
  3. 记录错误日志，便于调试

## 10. 实验生命周期管理

### 改动内容：
```python
def start_control(self):
    # 记录实验开始时间
    self.start_time = time.time()
    self.current_experiment_data['start_time'] = self.start_time
    # 清空当前实验数据，保留历史数据

def stop_control(self):
    # 记录实验结束时间
    self.current_experiment_data['end_time'] = time.time()
    # 将当前实验数据保存到连续实验数据中
    self.continuous_data['experiments'].append(experiment_copy)
```

### 改动依据和思路：
- **设计目标**：完整追踪每次实验的生命周期
- **实现思路**：
  1. 在实验开始时初始化数据结构
  2. 在实验结束时归档数据到历史记录
  3. 为每次实验分配唯一ID，便于管理和追溯

## 11. 数据导出优化

### 改动内容：
```python
# 连续实验导出时添加实验摘要
summary_data = {
    'Experiment ID': [],
    'Start Time': [],
    'End Time': [],
    'Duration (s)': []
}
# 为每次实验生成摘要信息
```

### 改动依据和思路：
- **用户体验**：连续实验数据量大，需要概览信息
- **设计思路**：
  1. 主数据sheet存储详细数据
  2. 摘要sheet提供实验概览
  3. 包含时间戳、持续时间等关键信息

## 设计原则总结：

1. **数据完整性**：确保所有数据数组长度一致，即使出现错误也要保持结构完整
2. **功能分离**：单次和连续实验数据分开管理，避免相互影响
3. **错误容错**：异常情况下用合理默认值填充，而不是中断程序
4. **用户友好**：提供清晰的功能选择，满足不同使用场景
5. **数据溯源**：记录完整的时间信息和实验ID，便于后续分析

这种设计既解决了您提到的具体问题（数据缺失、连续保存），又为将来的功能扩展留出了空间。