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

2025.5.10
    1. 开放预热时间，加入材料参数保存 ☑️
    2. 处理采样率
    3. 串口反了
    4. 把文件选择的部分注释掉，该功能已经合并到export data  ☑️
    5. 直接start开始下一轮，会出现数据残缺的问题，main 和 其中一个传感器会缺少后半部份数据，考虑是不是缓存问题  ☑️
    6. 再次start的时候，export之后的数据是拼在前一组数组之后的，希望能有个新的功能是保留单次start和stop的试验结果  ☑️
    7. 点击pause之后，虽然可以回读数据并且可视化，但是export data导出的文件中并没有这段数据。
    8. 放大的图片中，希望鼠标放上去就能显示这个点的数值，因为温度曲线有好几条而且变化比较大，直接用肉眼对齐坐标轴不是很方便
    9. 保存的材料参数有效小数位只有两位，而且无法save和load，考虑是不是要把json文件分开打包  ☑️

class MaterialParamsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Material Parameters Management")
        self.setGeometry(200, 200, 450, 400)
        
        self.parent = parent  # 保存父窗口引用
        layout = QVBoxLayout()
        
        # 添加材料选择区域
        selection_group = QGroupBox("Select Material")
        selection_layout = QVBoxLayout()
        
        # 材料选择下拉框
        self.material_selector = QComboBox()
        self.material_selector.setEditable(False)
        self.material_selector.currentIndexChanged.connect(self.on_material_selected)
        selection_layout.addWidget(QLabel("Saved Materials:"))
        selection_layout.addWidget(self.material_selector)
        
        # 删除材料按钮
        self.delete_button = QPushButton("Delete Selected Material")
        self.delete_button.clicked.connect(self.delete_material)
        selection_layout.addWidget(self.delete_button)
        
        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)
        
        # 参数编辑区域
        params_group = QGroupBox("Material Parameters")
        params_layout = QVBoxLayout()
        
        # 材料名称输入
        self.material_name = QLineEdit()
        self.material_name.setPlaceholderText("Enter new material name")
        params_layout.addWidget(QLabel("Material name:"))
        params_layout.addWidget(self.material_name)
        
        # 参数输入
        self.initial_voltage = QDoubleSpinBox()
        self.initial_voltage.setRange(0, 30)
        self.initial_voltage.setSingleStep(0.1)
        self.initial_voltage.setValue(17.0)  # 默认值
        params_layout.addWidget(QLabel("Initial voltage (V):"))
        params_layout.addWidget(self.initial_voltage)
        
        self.kp = QDoubleSpinBox()
        self.kp.setRange(0, 100)
        self.kp.setSingleStep(0.1)
        self.kp.setValue(0.2)  # 默认值
        params_layout.addWidget(QLabel("Kp:"))
        params_layout.addWidget(self.kp)
        
        self.ki = QDoubleSpinBox()
        self.ki.setRange(0, 100)
        self.ki.setSingleStep(0.1)
        self.ki.setValue(0.002)  # 默认值
        params_layout.addWidget(QLabel("Ki:"))
        params_layout.addWidget(self.ki)
        
        self.kd = QDoubleSpinBox()
        self.kd.setRange(0, 100)
        self.kd.setSingleStep(0.1)
        self.kd.setValue(0.005)  # 默认值
        params_layout.addWidget(QLabel("Kd:"))
        params_layout.addWidget(self.kd)
        
        # 最大电压设置
        self.max_voltage = QDoubleSpinBox()
        self.max_voltage.setRange(1, 50)
        self.max_voltage.setSingleStep(0.1)
        self.max_voltage.setValue(7.0)  # 默认值
        params_layout.addWidget(QLabel("Maximum voltage (V):"))
        params_layout.addWidget(self.max_voltage)
        
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 保存当前参数按钮
        self.save_button = QPushButton("Save Current Parameters")
        self.save_button.clicked.connect(self.save_parameters)
        button_layout.addWidget(self.save_button)
        
        # 加载所选材料按钮
        self.load_button = QPushButton("Load Selected Material")
        self.load_button.clicked.connect(self.load_selected_material)
        button_layout.addWidget(self.load_button)
        
        layout.addLayout(button_layout)
        
        # 对话框按钮
        self.dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(self.dialog_buttons)
        
        self.setLayout(layout)
        
        # 初始加载所有已保存的材料
        self.update_material_list()
    
    def update_material_list(self):
        """更新材料选择下拉框"""
        self.material_selector.clear()
        
        # 添加一个空选项
        self.material_selector.addItem("-- Select Material --", None)
        
        # 如果有已保存的材料参数
        if hasattr(self.parent, "material_params") and self.parent.material_params:
            for material_name in self.parent.material_params.keys():
                self.material_selector.addItem(material_name, material_name)
    
    def on_material_selected(self, index):
        """处理材料选择变化事件"""
        if index <= 0:  # 空选项
            return
            
        material_name = self.material_selector.itemData(index)
        if material_name and hasattr(self.parent, "material_params"):
            # 加载选中材料的参数
            params = self.parent.material_params.get(material_name)
            if params:
                self.set_params(params)
                self.material_name.setText(material_name)  # 设置材料名称
    
    def get_params(self):
        """获取对话框中的参数值"""
        params = {
            "initial_voltage": self.initial_voltage.value(),
            "kp": self.kp.value(),
            "ki": self.ki.value(),
            "kd": self.kd.value(),
            "max_voltage": self.max_voltage.value()
        }
        return params
    
    def set_params(self, params):
        """设置参数值到对话框控件"""
        if not params:
            return
            
        if "initial_voltage" in params:
            self.initial_voltage.setValue(params["initial_voltage"])
        if "kp" in params:
            self.kp.setValue(params["kp"])
        if "ki" in params:
            self.ki.setValue(params["ki"])
        if "kd" in params:
            self.kd.setValue(params["kd"])
        if "max_voltage" in params:
            self.max_voltage.setValue(params["max_voltage"])
    
    def save_parameters(self):
        """保存当前参数"""
        # 获取材料名称
        material_name = self.material_name.text().strip()
        if not material_name:
            QMessageBox.warning(self, "Warning", "Please enter a material name")
            return
        
        # 获取当前参数
        params = self.get_params()
        
        # 检查父窗口的材料参数存储
        if not hasattr(self.parent, "material_params"):
            self.parent.material_params = {}
        
        # 询问用户是否覆盖现有材料
        if material_name in self.parent.material_params:
            reply = QMessageBox.question(
                self, 
                "Confirm Update", 
                f"Material '{material_name}' already exists. Update it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # 保存或更新材料参数
        self.parent.material_params[material_name] = params
        self.parent.save_material_params_to_file()
        
        # 更新材料列表
        self.update_material_list()
        
        # 选择刚才保存的材料
        index = self.material_selector.findData(material_name)
        if index >= 0:
            self.material_selector.setCurrentIndex(index)
        
        QMessageBox.information(self, "Success", f"Parameters for '{material_name}' have been saved")
    
    def load_selected_material(self):
        """加载选中的材料参数"""
        index = self.material_selector.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "Warning", "Please select a material first")
            return
        
        material_name = self.material_selector.itemData(index)
        if material_name and hasattr(self.parent, "material_params"):
            params = self.parent.material_params.get(material_name)
            if params:
                self.set_params(params)
                # 将材料参数应用到主窗口
                self.parent.apply_material_params(material_name, params)
                QMessageBox.information(self, "Success", f"Parameters for '{material_name}' have been loaded")
    
    def delete_material(self):
        """删除选中的材料"""
        index = self.material_selector.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "Warning", "Please select a material to delete")
            return
        
        material_name = self.material_selector.itemData(index)
        if not material_name:
            return
        
        # 询问用户确认删除
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            f"Are you sure you want to delete material '{material_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes and hasattr(self.parent, "material_params"):
            # 删除材料
            if material_name in self.parent.material_params:
                del self.parent.material_params[material_name]
                self.parent.save_material_params_to_file()
                
                # 更新材料列表
                self.update_material_list()
                self.material_selector.setCurrentIndex(0)  # 重置选择
                
                QMessageBox.information(self, "Success", f"Material '{material_name}' has been deleted")

def __init__(self):
    # ... 现有代码 ...
    
    # 修改材料参数初始化
    self.material_params = {}  # 改为空字典，不是None
    self.load_material_params()  # 加载保存的参数

def save_material_params_to_file(self):
    """保存材料参数到文件"""
    if self.material_params:
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.material_params, f, indent=4)
            print(f"材料参数已保存到: {self.config_file}")
        except Exception as e:
            print(f"保存材料参数失败: {e}")

def load_material_params(self):
    """从文件加载材料参数"""
    try:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.material_params = json.load(f)
                print(f"已加载{len(self.material_params)}组材料参数")
        else:
            self.material_params = {}
            print("材料参数文件不存在，使用空字典")
    except Exception as e:
        print(f"加载材料参数失败: {e}")
        self.material_params = {}

def apply_material_params(self, material_name, params):
    """将材料参数应用到控制参数输入框"""
    if not params:
        return
        
    # 设置初始电压
    if "initial_voltage" in params:
        self.initial_voltage_input.setText(str(params["initial_voltage"]))
    
    # 设置PID参数
    if "kp" in params:
        self.kp_input.setText(str(params["kp"]))
    if "ki" in params:
        self.ki_input.setText(str(params["ki"]))
    if "kd" in params:
        self.kd_input.setText(str(params["kd"]))
    
    # 设置最大电压
    if "max_voltage" in params:
        self.max_voltage_input.setText(str(params["max_voltage"]))
        
    QMessageBox.information(
        self, 
        "Material Parameters Loaded", 
        f"Parameters for '{material_name}' have been applied to control settings"
    )

def update_plots(self):
    if self.pid_controller and self.pid_controller.modbus_sensor:
        current_time = time.time() - self.start_time if hasattr(self, 'start_time') else 0
        
        # 更明确的状态判断
        if not hasattr(self, 'warmup_completed'):
            current_state = 'warmup'
        elif self.is_paused:
            current_state = 'pause'
        else:
            current_state = 'control'

def export_single_experiment(self):
    # ... 现有代码 ...
    
    # 添加更详细的实验阶段统计
    state_stats = {
        'Phase': ['Warm-up', 'PID Control', 'Pause'],
        'Duration (s)': [
            sum(1 for x in self.current_experiment_data['data_states'] if x == 'warmup'),
            sum(1 for x in self.current_experiment_data['data_states'] if x == 'control'),
            sum(1 for x in self.current_experiment_data['data_states'] if x == 'pause')
        ],
        'Start Time': [
            self.current_experiment_data['time'][0] if self.current_experiment_data['time'] else None,
            self.current_experiment_data['time'][self.current_experiment_data['data_states'].index('control')] if 'control' in self.current_experiment_data['data_states'] else None,
            self.current_experiment_data['time'][self.current_experiment_data['data_states'].index('pause')] if 'pause' in self.current_experiment_data['data_states'] else None
        ]
    }

def export_continuous_experiments(self):
    # ... 现有代码 ...
    
    # 添加每个实验的详细状态信息
    for experiment in self.continuous_data['experiments']:
        exp_data = experiment['data']
        state_counts = {
            'warmup': exp_data['data_states'].count('warmup'),
            'control': exp_data['data_states'].count('control'),
            'pause': exp_data['data_states'].count('pause')
        }
        experiment['state_stats'] = state_counts

def update_status_display(self):
    """更新状态显示"""
    if not self.is_running:
        self.status_label.setText("Status: Stopped")
        return
        
    if self.is_paused:
        self.status_label.setText("Status: Paused")
        return
        
    if not hasattr(self, 'warmup_completed'):
        self.status_label.setText("Status: Warm-up")
    else:
        self.status_label.setText("Status: PID Control")

