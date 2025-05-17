import sys
import os
import platform
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QPushButton, 
                           QLabel, QLineEdit, QWidget, QListWidget, QListWidgetItem, 
                           QTextEdit, QComboBox, QHBoxLayout, QFileDialog, QScrollArea, QDialog, QDateTimeEdit, QDialogButtonBox, QDoubleSpinBox, QInputDialog, QMessageBox, QGroupBox)
from PyQt5.QtCore import QTimer, Qt, QDateTime, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QColor
import pyqtgraph as pg
from center_control import PIDController
from MOD_700 import ModbusSensor
from power import PowerSupply
import serial.tools.list_ports
from datetime import datetime
import json
from appdirs import user_data_dir
import time
from collections import deque
import numpy as np
import logging
import traceback

class Logger:
    """日志管理类，用于记录程序运行日志"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """初始化日志系统"""
        # 获取配置目录
        if platform.system() == 'Windows':
            self.config_dir = os.path.join(os.environ['APPDATA'], 'PIDTempControl', 'Personal')
        else:
            self.config_dir = user_data_dir('PIDTempControl', 'Personal')
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 设置日志文件路径
        self.log_file = os.path.join(self.config_dir, 'pid_control.log')
        
        # 配置日志记录器
        self.logger = logging.getLogger('PIDControl')
        self.logger.setLevel(logging.DEBUG)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 设置格式化器
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message):
        """记录调试信息"""
        self.logger.debug(message)
    
    def info(self, message):
        """记录一般信息"""
        self.logger.info(message)
    
    def warning(self, message):
        """记录警告信息"""
        self.logger.warning(message)
    
    def error(self, message):
        """记录错误信息"""
        self.logger.error(message)
    
    def critical(self, message):
        """记录严重错误信息"""
        self.logger.critical(message)
    
    def exception(self, message):
        """记录异常信息，包含堆栈跟踪"""
        self.logger.exception(message)
    
    def get_log_file_path(self):
        """获取日志文件路径"""
        return self.log_file

# 创建全局日志记录器实例
logger = Logger()

class ControlThread(QThread):
    """控制线程类，用于在后台运行PID控制"""
    finished = pyqtSignal()  # 控制完成信号
    
    def __init__(self, pid_controller):
        super().__init__()
        self.pid_controller = pid_controller
        self.is_running = True
        self.is_paused = False
        
    def run(self):
        """运行控制线程"""
        logger.info("控制线程开始运行")
        while self.is_running:
            if not self.is_paused:
                try:
                    # 读取当前温度
                    if self.pid_controller.modbus_sensor and self.pid_controller.main_sensor:
                        current_temp = self.pid_controller.modbus_sensor.read_temperature(self.pid_controller.main_sensor)
                        if current_temp is not None:
                            logger.debug(f"\n=== PID控制循环 ===")
                            logger.debug(f"读取到主传感器温度: {current_temp}°C")
                            logger.debug(f"PID控制器状态: running={self.pid_controller.is_running}, paused={self.pid_controller.is_paused}")
                            # 执行PID控制
                            self.pid_controller.update(current_temp)
                            logger.debug("=== PID控制循环完成 ===\n")
                        else:
                            logger.warning("无法读取主传感器温度")
                    else:
                        logger.warning("温度传感器或主传感器未设置")
                except Exception as e:
                    logger.error(f"PID控制执行失败: {e}")
                    logger.exception("PID控制执行失败")
            else:
                logger.info("控制已暂停")
            self.msleep(self.pid_controller.sampling_rate)  # 使用PID控制器的采样率
        logger.info("控制线程停止运行")
        self.finished.emit()
        
    def stop(self):
        """停止控制线程"""
        logger.info("正在停止控制线程...")
        self.is_running = False
        self.is_paused = False
        if self.pid_controller:
            self.pid_controller.stop()
        
    def pause(self):
        """暂停控制线程"""
        self.is_paused = True
        if self.pid_controller:
            self.pid_controller.pause()
        
    def resume(self):
        """恢复控制线程"""
        self.is_paused = False
        if self.pid_controller:
            self.pid_controller.resume()

class EnlargedPlotWindow(QMainWindow):
    def __init__(self, plot_widget, title):
        super().__init__()
        self.setWindowTitle(f"Enlarged {title}")
        # 设置窗口位置，避免重叠
        self.setGeometry(100, 100, 800, 600)
        self.plot_widget = plot_widget  # 保存原始图表引用
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 复制原始图表
        self.plot = pg.PlotWidget()
        self.plot.setLabel('left', plot_widget.getAxis('left').labelText)
        self.plot.setLabel('bottom', plot_widget.getAxis('bottom').labelText)
        
        # 创建数据提示标签
        self.data_tip = pg.TextItem(
            text='',
            color=(0, 0, 0),
            border=pg.mkPen(color=(0, 0, 0)),
            fill=pg.mkBrush(color=(255, 255, 255, 180))
        )
        self.data_tip.hide()
        self.plot.addItem(self.data_tip)
        
        # 复制所有曲线
        self.curves = {}  # 存储曲线引用
        for item in plot_widget.items():
            if isinstance(item, pg.PlotDataItem):
                try:
                    # 获取曲线数据
                    x_data = item.xData
                    y_data = item.yData
                    
                    # 只有当数据存在时才创建新曲线
                    if x_data is not None and y_data is not None:
                        # 获取曲线名称
                        name = item.name() if item.name() else 'Unknown'
                        # 创建新曲线
                        new_curve = self.plot.plot(pen=item.opts['pen'], name=name)
                        new_curve.setData(x_data, y_data)
                        # 保存曲线引用和数据
                        self.curves[name] = {
                            'curve': new_curve,
                            'x_data': x_data,
                            'y_data': y_data
                        }
                except Exception as e:
                    print(f"Error copying curve data: {e}")
        
        # 添加图例
        self.plot.addLegend()
        
        # 设置交互功能
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        
        # 连接鼠标移动事件
        self.plot.scene().sigMouseMoved.connect(self.mouse_moved)
        
        layout.addWidget(self.plot)
        
        # 添加关闭按钮
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def mouse_moved(self, pos):
        """处理鼠标移动事件"""
        if self.plot.sceneBoundingRect().contains(pos):
            mouse_point = self.plot.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # 查找最近的曲线点
            closest_curve = None
            closest_point = None
            min_distance = float('inf')
            
            for name, curve_data in self.curves.items():
                x_data = curve_data['x_data']
                y_data = curve_data['y_data']
                
                # 找到最近的数据点
                for i in range(len(x_data)):
                    dx = x_data[i] - x
                    dy = y_data[i] - y
                    distance = (dx * dx + dy * dy) ** 0.5
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_curve = name
                        closest_point = (x_data[i], y_data[i])
            
            # 如果找到足够近的点（距离小于某个阈值）
            if min_distance < 0.1:  # 可以调整这个阈值
                # 更新数据提示文本
                text = f"{closest_curve}\nX: {closest_point[0]:.2f}\nY: {closest_point[1]:.2f}"
                self.data_tip.setText(text)
                
                # 设置数据提示位置
                self.data_tip.setPos(closest_point[0], closest_point[1])
                self.data_tip.show()
            else:
                self.data_tip.hide()
        else:
            self.data_tip.hide()

    def update_plot(self, plot_widget):
        """更新放大窗口中的图表数据"""
        # 清除现有曲线
        self.plot.clear()
        self.curves.clear()
        
        # 重新添加数据提示标签
        self.data_tip = pg.TextItem(
            text='',
            color=(0, 0, 0),
            border=pg.mkPen(color=(0, 0, 0)),
            fill=pg.mkBrush(color=(255, 255, 255, 180))
        )
        self.data_tip.hide()
        self.plot.addItem(self.data_tip)
        
        # 复制所有曲线
        for item in plot_widget.items():
            if isinstance(item, pg.PlotDataItem):
                try:
                    # 获取曲线数据
                    x_data = item.xData
                    y_data = item.yData
                    
                    # 只有当数据存在时才创建新曲线
                    if x_data is not None and y_data is not None:
                        # 获取曲线名称
                        name = item.name() if item.name() else 'Unknown'
                        # 创建新曲线
                        new_curve = self.plot.plot(pen=item.opts['pen'], name=name)
                        new_curve.setData(x_data, y_data)
                        # 保存曲线引用和数据
                        self.curves[name] = {
                            'curve': new_curve,
                            'x_data': x_data,
                            'y_data': y_data
                        }
                except Exception as e:
                    print(f"Error updating curve data: {e}")
        
        # 重新添加图例
        self.plot.addLegend()
        
        # 设置交互功能
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()

class MaterialParamsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Material Parameters Management")
        self.setGeometry(200, 200, 500, 500)  # 增加对话框高度以容纳新参数
        
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
        
        # 目标温度设置
        self.target_temp = QDoubleSpinBox()
        self.target_temp.setRange(0, 500)  # 修改最大值为500
        self.target_temp.setSingleStep(0.1)  # 保持步进值为0.1
        self.target_temp.setDecimals(1)  # 设置小数位数为1位
        self.target_temp.setValue(60.0)  # 默认值
        params_layout.addWidget(QLabel("Target Temperature (°C):"))
        params_layout.addWidget(self.target_temp)
        
        # 初始电压输入
        self.initial_voltage = QDoubleSpinBox()
        self.initial_voltage.setRange(0, 30)
        self.initial_voltage.setSingleStep(0.1)
        self.initial_voltage.setValue(17.0)  # 默认值
        params_layout.addWidget(QLabel("Initial voltage (V):"))
        params_layout.addWidget(self.initial_voltage)
        
        # 最大电压设置
        self.max_voltage = QDoubleSpinBox()
        self.max_voltage.setRange(1, 50)
        self.max_voltage.setSingleStep(0.1)
        self.max_voltage.setValue(7.0)  # 默认值
        params_layout.addWidget(QLabel("Maximum voltage (V):"))
        params_layout.addWidget(self.max_voltage)
        
        # 预热时间设置
        self.warmup_time = QDoubleSpinBox()
        self.warmup_time.setRange(0, 300)
        self.warmup_time.setSingleStep(1.0)
        self.warmup_time.setValue(20.0)  # 默认值
        params_layout.addWidget(QLabel("Warm-up Time (s):"))
        params_layout.addWidget(self.warmup_time)
        
        # PID参数
        pid_group = QGroupBox("PID Parameters")
        pid_layout = QVBoxLayout()
        
        self.kp = QDoubleSpinBox()
        self.kp.setRange(0, 100)
        self.kp.setSingleStep(0.0001)
        self.kp.setDecimals(6)  # 提高到6位小数精度
        self.kp.setValue(0.2)  # 默认值
        pid_layout.addWidget(QLabel("Kp:"))
        pid_layout.addWidget(self.kp)
        
        self.ki = QDoubleSpinBox()
        self.ki.setRange(0, 100)
        self.ki.setSingleStep(0.0001)
        self.ki.setDecimals(6)  # 提高到6位小数精度
        self.ki.setValue(0.002)  # 默认值
        pid_layout.addWidget(QLabel("Ki:"))
        pid_layout.addWidget(self.ki)
        
        self.kd = QDoubleSpinBox()
        self.kd.setRange(0, 100)
        self.kd.setSingleStep(0.0001)
        self.kd.setDecimals(6)  # 提高到6位小数精度
        self.kd.setValue(0.005)  # 默认值
        pid_layout.addWidget(QLabel("Kd:"))
        pid_layout.addWidget(self.kd)
        
        pid_group.setLayout(pid_layout)
        params_layout.addWidget(pid_group)
        
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
        
        # 添加配置文件路径显示按钮
        path_button = QPushButton("Show Config File Path")
        path_button.clicked.connect(self.show_config_path)
        layout.addWidget(path_button)
        
        self.setLayout(layout)
        
        # 初始加载所有已保存的材料
        self.update_material_list()
    
    def show_config_path(self):
        """显示配置文件路径"""
        if hasattr(self.parent, "config_file"):
            QMessageBox.information(
                self,
                "Configuration File Path",
                f"Material parameters are saved at:\n{self.parent.config_file}"
            )
    
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
            "max_voltage": self.max_voltage.value(),
            "target_temp": self.target_temp.value(),
            "warmup_time": self.warmup_time.value(),
            "kp": self.kp.value(),
            "ki": self.ki.value(),
            "kd": self.kd.value()
        }
        return params
    
    def set_params(self, params):
        """设置参数值到对话框控件"""
        if not params:
            return
            
        if "initial_voltage" in params:
            self.initial_voltage.setValue(params["initial_voltage"])
        if "max_voltage" in params:
            self.max_voltage.setValue(params["max_voltage"])
        if "target_temp" in params:
            self.target_temp.setValue(params["target_temp"])
        if "warmup_time" in params:
            self.warmup_time.setValue(params["warmup_time"])
        if "kp" in params:
            self.kp.setValue(params["kp"])
        if "ki" in params:
            self.ki.setValue(params["ki"])
        if "kd" in params:
            self.kd.setValue(params["kd"])
    
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

def handle_windows_error(e):
    """处理 Windows 特定的错误"""
    if platform.system() == 'Windows':
        if "Access denied" in str(e):
            return "请以管理员权限运行程序"
        elif "COM port" in str(e):
            return "串口访问失败，请检查设备连接和权限"
    return str(e)

class PIDSystemUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PID Temperature Control System")
        self.setGeometry(100, 100, 1200, 800)
        
        # 获取配置目录
        if platform.system() == 'Windows':
            self.config_dir = os.path.join(os.environ['APPDATA'], 'PIDTempControl', 'Personal')
        else:
            self.config_dir = user_data_dir('PIDTempControl', 'Personal')
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, 'material_params.json')
        
        # 存储放大窗口的字典
        self.enlarged_windows = {}
        # 窗口位置计数器
        self.window_position = 0
        
        # 初始化PID控制器
        self.pid_controller = PIDController()
        self.pid_controller.system_time_data = deque(maxlen=1000)
        
        # 初始化数据存储
        self.control_data = {
            'time': [],
            'temperatures': {},
            'voltage': [],
            'current': [],
            'data_states': []  # 新增：记录每个数据点的状态
        }
        
        # 添加连续实验数据存储
        self.continuous_data = {
            'experiments': [],  # 存储每次实验的数据
            'experiment_count': 0
        }
        
        # 添加当前实验数据存储
        self.current_experiment_data = {
            'time': [],
            'temperatures': {},
            'voltage': [],
            'current': [],
            'start_time': None,
            'end_time': None,
            'data_states': []  # 新增：记录每个数据点的状态
        }
        
        self.init_ui()
        self.material_params = {}  # 使用字典存储材料参数
        self.load_material_params()  # 加载保存的参数

    def init_ui(self):
        # 创建主窗口部件和布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()
        
        # 左侧面板（传感器选择）
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout()
        self.left_panel.setLayout(self.left_layout)
        self.main_layout.addWidget(self.left_panel, stretch=1)

        # 中间面板（图表）
        self.center_panel = QWidget()
        self.center_layout = QVBoxLayout()
        self.center_panel.setLayout(self.center_layout)
        self.main_layout.addWidget(self.center_panel, stretch=2)

        # 右侧面板（控制按钮和设置）
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout()
        self.right_panel.setLayout(self.right_layout)
        self.main_layout.addWidget(self.right_panel, stretch=1)

        # 初始化图表
        self.init_plots()

        # 添加各个面板的组件
        self.add_left_panel_components()
        self.add_right_panel_components()

        self.central_widget.setLayout(self.main_layout)

        # 初始化定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status)
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)
        self.modbus_sensor = None
        self.elapsed_seconds = 0
        self.target_duration = 0
        self.selected_sensors = []  # 存储选中的传感器列表
        self.main_sensor = None  # 主传感器（用于PID控制）

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

    def add_left_panel_components(self):
        """添加左侧面板组件"""
        # 传感器选择区域
        sensor_group = QGroupBox("Sensor Selection")
        sensor_layout = QVBoxLayout()

        # 传感器列表
        self.sensor_list = QListWidget()
        self.sensor_list.setSelectionMode(QListWidget.MultiSelection)
        for i in range(1, 61):
            self.sensor_list.addItem(f"Sensor {i}")
        
        # 连接双击事件
        self.sensor_list.itemDoubleClicked.connect(self.on_sensor_double_clicked)
        # 连接单击事件
        self.sensor_list.itemClicked.connect(self.on_sensor_clicked)
        
        sensor_layout.addWidget(self.sensor_list)
        sensor_group.setLayout(sensor_layout)
        self.left_layout.addWidget(sensor_group)

        # 已选传感器显示区域
        self.selected_sensors_label = QLabel("Selected Sensors:")
        self.selected_sensors_display = QListWidget()
        self.left_layout.addWidget(self.selected_sensors_label)
        self.left_layout.addWidget(self.selected_sensors_display)

        # 添加分隔线
        self.left_layout.addWidget(QLabel("---"))

        # 数据采集设置
        self.sampling_label = QLabel("Data Sampling Settings:")
        self.left_layout.addWidget(self.sampling_label)

        # 采样速率设置
        self.sampling_rate_layout = QHBoxLayout()
        self.sampling_rate_label = QLabel("Sampling Rate (ms):")
        self.sampling_rate_input = QLineEdit()
        self.sampling_rate_input.setText("30")  # 默认30ms
        self.sampling_rate_layout.addWidget(self.sampling_rate_label)
        self.sampling_rate_layout.addWidget(self.sampling_rate_input)
        self.left_layout.addLayout(self.sampling_rate_layout)

        # 添加分隔线
        self.left_layout.addWidget(QLabel("---"))

        # 控制参数设置
        self.control_params_label = QLabel("Control Parameters:")
        self.left_layout.addWidget(self.control_params_label)

        # 初始电压输入
        self.initial_voltage_label = QLabel("Initial Voltage (V):")
        self.left_layout.addWidget(self.initial_voltage_label)
        self.initial_voltage_input = QLineEdit()
        self.initial_voltage_input.setText("17.0")
        self.left_layout.addWidget(self.initial_voltage_input)

        # 目标温度输入
        self.setpoint_label = QLabel("Setpoint Temperature:")
        self.left_layout.addWidget(self.setpoint_label)
        self.setpoint_input = QLineEdit()
        self.left_layout.addWidget(self.setpoint_input)

        # 持续时间设置
        self.duration_label = QLabel("Duration (minutes):")
        self.left_layout.addWidget(self.duration_label)
        self.duration_input = QLineEdit()
        self.duration_input.setText("30")
        self.left_layout.addWidget(self.duration_input)

        # 温度误差范围设置
        self.tolerance_label = QLabel("Temperature Tolerance (°C):")
        self.left_layout.addWidget(self.tolerance_label)
        self.tolerance_input = QLineEdit()
        self.tolerance_input.setText("0.5")
        self.left_layout.addWidget(self.tolerance_input)

        # 最大电压限制设置
        self.max_voltage_label = QLabel("Maximum Voltage (V):")
        self.left_layout.addWidget(self.max_voltage_label)
        self.max_voltage_input = QLineEdit()
        self.max_voltage_input.setText("7.0")  # 默认7V
        self.left_layout.addWidget(self.max_voltage_input)

        # 预热时间设置
        self.warmup_label = QLabel("Warm-up Time (s):")
        self.left_layout.addWidget(self.warmup_label)
        self.warmup_input = QLineEdit()
        self.warmup_input.setText("20")  # 默认20秒
        self.left_layout.addWidget(self.warmup_input)

        # 添加弹性空间
        self.left_layout.addStretch()

    def add_right_panel_components(self):
        """添加右侧面板组件"""
        # 串口设置
        self.port_settings_label = QLabel("Port Settings:")
        self.right_layout.addWidget(self.port_settings_label)

        # 温度传感器串口选择
        self.temp_sensor_port_label = QLabel("Temperature Sensor Port:")
        self.right_layout.addWidget(self.temp_sensor_port_label)
        self.temp_sensor_port_combo = QComboBox()
        self.temp_sensor_port_combo.addItems(self.get_available_ports())
        self.right_layout.addWidget(self.temp_sensor_port_combo)

        # 电源发生器串口选择
        self.power_supply_port_label = QLabel("Power Supply Port:")
        self.right_layout.addWidget(self.power_supply_port_label)
        self.power_supply_port_combo = QComboBox()
        self.power_supply_port_combo.addItems(self.get_available_ports())
        self.right_layout.addWidget(self.power_supply_port_combo)

        # 添加分隔线
        self.right_layout.addWidget(QLabel("---"))

        # 将原来的测试按钮替换为按钮组
        test_button_layout = QHBoxLayout()
        self.start_test_button = QPushButton("Start Temperature Test")
        self.stop_test_button = QPushButton("Stop Temperature Test")
        self.start_test_button.clicked.connect(self.start_temperature_test)
        self.stop_test_button.clicked.connect(self.stop_temperature_test)
        self.stop_test_button.setEnabled(False)  # 初始时停止按钮禁用
        test_button_layout.addWidget(self.start_test_button)
        test_button_layout.addWidget(self.stop_test_button)
        self.right_layout.addLayout(test_button_layout)

        # 测试状态显示
        self.test_status_label = QLabel("Test Status: Not Started")
        self.right_layout.addWidget(self.test_status_label)

        # 添加分隔线
        self.right_layout.addWidget(QLabel("---"))

        # 添加日志文件路径显示按钮
        log_button = QPushButton("Show Log File Path")
        log_button.clicked.connect(self.show_log_file_path)
        self.right_layout.addWidget(log_button)

        # 添加分隔线
        self.right_layout.addWidget(QLabel("---"))

        # PID参数设置
        self.pid_label = QLabel("PID Parameters:")
        self.right_layout.addWidget(self.pid_label)

        # Kp设置
        self.kp_layout = QHBoxLayout()
        self.kp_label = QLabel("Kp:")
        self.kp_input = QLineEdit()
        self.kp_input.setText("0.2")
        self.kp_layout.addWidget(self.kp_label)
        self.kp_layout.addWidget(self.kp_input)
        self.right_layout.addLayout(self.kp_layout)

        # Ki设置
        self.ki_layout = QHBoxLayout()
        self.ki_label = QLabel("Ki:")
        self.ki_input = QLineEdit()
        self.ki_input.setText("0.002")
        self.ki_layout.addWidget(self.ki_label)
        self.ki_layout.addWidget(self.ki_input)
        self.right_layout.addLayout(self.ki_layout)

        # Kd设置
        self.kd_layout = QHBoxLayout()
        self.kd_label = QLabel("Kd:")
        self.kd_input = QLineEdit()
        self.kd_input.setText("0.005")
        self.kd_layout.addWidget(self.kd_label)
        self.kd_layout.addWidget(self.kd_input)
        self.right_layout.addLayout(self.kd_layout)

        # 添加分隔线
        self.right_layout.addWidget(QLabel("---"))

        # 数据保存设置
        self.save_settings_label = QLabel("Data Save Settings:")
        self.right_layout.addWidget(self.save_settings_label)

        # 保存目录选择
        # self.save_dir_layout = QHBoxLayout()
        # self.save_dir_label = QLabel("Save Directory:")
        # self.save_dir_input = QLineEdit()
        # self.save_dir_input.setReadOnly(True)
        # self.save_dir_button = QPushButton("Browse")
        # self.save_dir_button.clicked.connect(self.select_save_directory)
        # self.save_dir_layout.addWidget(self.save_dir_label)
        # self.save_dir_layout.addWidget(self.save_dir_input)
        # self.save_dir_layout.addWidget(self.save_dir_button)
        # self.right_layout.addLayout(self.save_dir_layout)

        # 添加分隔线
        self.right_layout.addWidget(QLabel("---"))

        # 控制按钮区域
        self.control_buttons_layout = QVBoxLayout()

        # 启动按钮
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_control)
        self.control_buttons_layout.addWidget(self.start_button)

        # 暂停按钮
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_control)
        self.control_buttons_layout.addWidget(self.pause_button)

        # 停止按钮
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_control)
        self.control_buttons_layout.addWidget(self.stop_button)

        # 导出数据按钮
        # self.export_button = QPushButton("Export Data")
        # self.export_button.clicked.connect(self.export_data)
        # self.control_buttons_layout.addWidget(self.export_button)
        # 两个导出数据的按钮，一个是连续保存的，一个是单次实验的数据
        export_layout = QHBoxLayout()
        self.export_single_button = QPushButton("Export Current Experiment")
        self.export_single_button.clicked.connect(self.export_single_experiment)
        export_layout.addWidget(self.export_single_button)
        self.export_continuous_button = QPushButton("Export All Experiments")
        self.export_continuous_button.clicked.connect(self.export_continuous_experiments)
        export_layout.addWidget(self.export_continuous_button)
        self.control_buttons_layout.addLayout(export_layout)
        
        # 状态显示区域
        self.status_layout = QVBoxLayout()
        
        # 状态显示
        self.status_label = QLabel("Status: Stopped")
        self.status_layout.addWidget(self.status_label)

        # 计时器显示
        self.timer_label = QLabel("Elapsed Time: 0:00")
        self.status_layout.addWidget(self.timer_label)

        self.right_layout.addLayout(self.status_layout)

        # 添加弹性空间
        self.right_layout.addStretch()

        # 在右侧控制面板添加材料参数管理按钮
        material_button = QPushButton("材料参数管理")
        material_button.clicked.connect(self.show_material_params_dialog)
        self.right_layout.addWidget(material_button)

    def init_plots(self):
        """初始化图表"""
        # 电压图表
        self.voltage_plot = pg.PlotWidget()
        self.voltage_plot.setLabel('left', 'Voltage', 'V')
        self.voltage_plot.setLabel('bottom', 'Time', 's')
        self.voltage_plot.setYRange(0, 30)  # 只设置Y轴范围
        self.voltage_curve = self.voltage_plot.plot(pen='r', name='Voltage')
        self.voltage_plot.addLegend()
        self.voltage_plot.scene().sigMouseClicked.connect(lambda evt: self.enlarge_plot(evt, self.voltage_plot, "Voltage Plot"))
        self.center_layout.addWidget(self.voltage_plot)

        # 电流图表
        self.current_plot = pg.PlotWidget()
        self.current_plot.setLabel('left', 'Current', 'A')
        self.current_plot.setLabel('bottom', 'Time', 's')
        self.current_plot.setYRange(0, 5)  # 只设置Y轴范围
        self.current_curve = self.current_plot.plot(pen='g', name='Current')
        self.current_plot.addLegend()
        self.current_plot.scene().sigMouseClicked.connect(lambda evt: self.enlarge_plot(evt, self.current_plot, "Current Plot"))
        self.center_layout.addWidget(self.current_plot)

        # 温度图表
        self.temperature_plot = pg.PlotWidget()
        self.temperature_plot.setLabel('left', 'Temperature', '°C')
        self.temperature_plot.setLabel('bottom', 'Time', 's')
        self.temperature_plot.setYRange(0, 100)  # 只设置Y轴范围
        self.temperature_curves = {}  # 存储温度曲线
        self.temperature_plot.addLegend()
        # 添加图例点击事件
        self.temperature_plot.scene().sigMouseClicked.connect(self.handle_legend_click)
        self.temperature_plot.scene().sigMouseClicked.connect(lambda evt: self.enlarge_plot(evt, self.temperature_plot, "Temperature Plot"))
        self.center_layout.addWidget(self.temperature_plot)
        
        # 确保图表可见
        self.temperature_plot.enableAutoRange()
        self.temperature_plot.setMouseEnabled(x=True, y=True)
        self.temperature_plot.show()
        
        # 强制更新图表
        self.temperature_plot.update()

    def on_sensor_double_clicked(self, item):
        """处理传感器双击事件"""
        sensor_num = int(item.text().split()[1])
        
        if sensor_num == self.main_sensor:
            # 如果双击的是当前主传感器，则完全取消选择
            self.main_sensor = None
            if sensor_num in self.selected_sensors:
                self.selected_sensors.remove(sensor_num)
        else:
            # 如果双击的是其他传感器，则将其设为主传感器
            if self.main_sensor is not None:
                # 如果已有主传感器，将其移到普通选中列表
                self.selected_sensors.append(self.main_sensor)
            self.main_sensor = sensor_num
            if sensor_num in self.selected_sensors:
                self.selected_sensors.remove(sensor_num)
        
        # 更新显示
        self.update_selected_sensors_display()
        if self.pid_controller:
            self.pid_controller.set_selected_sensors(self.selected_sensors, self.main_sensor)
        # 清除传感器列表中的选择状态
        self.sensor_list.clearSelection()

    def on_sensor_clicked(self, item):
        """处理传感器单击事件"""
        sensor_num = int(item.text().split()[1])
        
        if sensor_num == self.main_sensor:
            # 如果单击的是主传感器，不做任何操作
            return
            
        if sensor_num in self.selected_sensors:
            # 如果传感器已被选中，则取消选择
            self.selected_sensors.remove(sensor_num)
        else:
            # 如果传感器未被选中，则添加到选中列表
            self.selected_sensors.append(sensor_num)
        
        # 更新显示
        self.update_selected_sensors_display()
        if self.pid_controller:
            self.pid_controller.set_selected_sensors(self.selected_sensors, self.main_sensor)
        # 清除传感器列表中的选择状态
        self.sensor_list.clearSelection()

    def update_selected_sensors_display(self):
        """更新已选传感器显示"""
        self.selected_sensors_display.clear()
        
        # 显示主传感器（如果有）
        if self.main_sensor is not None:
            main_item = QListWidgetItem(f"Sensor {self.main_sensor} (Main)")
            main_item.setForeground(QColor("red"))  # 主传感器显示为红色
            self.selected_sensors_display.addItem(main_item)
        
        # 显示其他选中的传感器
        for sensor in sorted(self.selected_sensors):
            item = QListWidgetItem(f"Sensor {sensor}")
            self.selected_sensors_display.addItem(item)

    def start_control(self):
        """开始控制"""
        if not self.main_sensor:
            QMessageBox.warning(self, "Warning", "Please double-click to select a main sensor for PID control!")
            return
            
        # 检查目标温度是否设置
        target_temp = self.setpoint_input.text()
        if not target_temp:
            QMessageBox.warning(self, "警告", "请设置目标温度")
            return
        try:
            target_temp = float(target_temp)
            if target_temp <= 0:
                QMessageBox.warning(self, "警告", "目标温度必须大于0")
                return
        except ValueError:
            QMessageBox.warning(self, "警告", "目标温度必须是有效的数字")
            return
            
        # 检查保存目录是否设置
        if not self.save_dir_input.text():
            QMessageBox.warning(self, "警告", "请设置数据保存目录")
            return
            
        # 获取其他参数
        kp = float(self.kp_input.text())
        ki = float(self.ki_input.text())
        kd = float(self.kd_input.text())
        sampling_rate = self.sampling_rate_input.text()
        initial_voltage = float(self.initial_voltage_input.text())
        duration = float(self.duration_input.text())
        temp_error = float(self.tolerance_input.text())
        warmup_time = float(self.warmup_input.text())  # 获取预热时间
        
        # 检查最大电压设置
        try:
            max_voltage = float(self.max_voltage_input.text())
            if max_voltage <= 0:
                QMessageBox.warning(self, "警告", "最大电压必须大于0")
                return
            if max_voltage > 50:  # 安全限制
                QMessageBox.warning(self, "警告", "最大电压不能超过50V")
                return
        except ValueError:
            QMessageBox.warning(self, "警告", "最大电压必须是有效的数字")
            return

        # 设置PID参数
        self.pid_controller.set_pid_params(kp, ki, kd)
        self.pid_controller.set_sampling_rate(sampling_rate)
        self.pid_controller.set_initial_voltage(initial_voltage)
        self.pid_controller.set_target_temp(target_temp)
        self.pid_controller.set_duration(duration)
        self.pid_controller.set_temp_error(temp_error)
        self.pid_controller.set_warmup_time(warmup_time)  # 设置预热时间
        self.pid_controller.set_max_voltage(max_voltage)  # 设置最大电压限制
        
        # 连接温度传感器
        temp_sensor_port = self.temp_sensor_port_combo.currentText()
        try:
            if not self.pid_controller.connect_sensor(temp_sensor_port):
                QMessageBox.warning(self, "警告", "连接温度传感器失败")
                return
        except Exception as e:
            error_msg = handle_windows_error(e)
            QMessageBox.warning(self, "警告", f"连接温度传感器失败: {error_msg}")
            return
            
        # 连接电源发生器
        try:
            power_supply_port = self.power_supply_port_combo.currentText()
            if not self.pid_controller.connect_power_supply(power_supply_port):
                QMessageBox.warning(self, "警告", "连接电源发生器失败")
                return
        except Exception as e:
            error_msg = handle_windows_error(e)
            QMessageBox.warning(self, "错误", f"连接电源发生器时出错: {error_msg}")
            return

        # 设置选中的传感器
        self.pid_controller.set_selected_sensors(self.selected_sensors, self.main_sensor)
        
        # 启动控制
        self.pid_controller.start()
        
        # 启动控制线程
        self.control_thread = ControlThread(self.pid_controller)
        self.control_thread.finished.connect(self.control_finished)
        self.control_thread.start()
        
        # 更新按钮状态
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        
        # 启动定时器更新显示
        self.timer.start(int(sampling_rate))  # 将采样率转换为整数
        
        # 启动计时器
        self.elapsed_timer.start(1000)  # 每秒更新一次
        self.is_running = True
        self.is_paused = False
        self.status_label.setText("Status: Running")
        
        # 记录开始时间
        self.start_time = time.time()
        
        # 清空当前实验数据，但保留连续实验数据
        self.current_experiment_data = {
            'time': [],
            'temperatures': {},
            'voltage': [],
            'current': [],
            'start_time': self.start_time,
            'end_time': None,
            'data_states': []  # 新增：记录每个数据点的状态
        }
        
        # 清空控制数据（用于实时显示）
        self.control_data = {
            'time': [],
            'temperatures': {},
            'voltage': [],
            'current': [],
            'data_states': []  # 新增：记录每个数据点的状态
        }

    def pause_control(self):
        if self.pid_controller and self.is_running and not self.is_paused:
            self.pid_controller.pause()
            self.is_paused = True
            self.status_label.setText("Status: Paused")
        elif self.pid_controller and self.is_running and self.is_paused:
            self.pid_controller.resume()
            self.is_paused = False
            self.status_label.setText("Status: Running")

    def stop_control(self):
        """停止控制"""
        logger.info("\n=== 开始停止控制 ===")
        
        # 立即停止所有定时器
        if hasattr(self, 'timer'):
            self.timer.stop()
            logger.info("已停止状态更新定时器")
        
        if hasattr(self, 'elapsed_timer'):
            self.elapsed_timer.stop()
            logger.info("已停止计时器")
        
        # 立即设置状态
        self.is_running = False
        self.is_paused = False
        self.status_label.setText("Status: Stopping...")
        
        # 立即停止PID控制器
        if self.pid_controller:
            try:
                logger.info("正在停止PID控制器...")
                # 先关闭电源输出
                if self.pid_controller.power_supply:
                    try:
                        self.pid_controller.power_supply.off_output()
                        logger.info("已关闭电源输出")
                    except Exception as e:
                        logger.error(f"关闭电源输出时发生错误: {e}")
                
                # 停止PID控制
                self.pid_controller.stop()
                logger.info("PID控制器已停止")
            except Exception as e:
                logger.error(f"停止PID控制器时发生错误: {e}")
        
        # 强制停止控制线程
        if hasattr(self, 'control_thread') and self.control_thread.isRunning():
            logger.info("正在停止控制线程...")
            try:
                # 先尝试正常停止
                self.control_thread.stop()
                self.control_thread.wait(1000)  # 等待1秒
                
                # 如果线程还在运行，强制终止
                if self.control_thread.isRunning():
                    logger.warning("控制线程未响应，强制终止...")
                    self.control_thread.terminate()
                    self.control_thread.wait(1000)  # 再等待1秒
                    
                    # 如果还是无法停止，使用更强制的方式
                    if self.control_thread.isRunning():
                        logger.warning("警告：控制线程无法正常停止，使用强制方式")
                        self.control_thread.quit()
            except Exception as e:
                logger.error(f"停止控制线程时发生错误: {e}")
        
        # 更新状态
        self.status_label.setText("Status: Stopped")
        self.elapsed_seconds = 0
        self.update_elapsed_time()
        
        # 更新按钮状态
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        
        # 清空数据
        self.control_data = {
            'time': [],
            'temperatures': {},
            'voltage': [],
            'current': [],
            'data_states': []  # 新增：记录每个数据点的状态
        }
        
        # 记录结束时间并保存当前实验数据
        if hasattr(self, 'start_time'):
            self.current_experiment_data['end_time'] = time.time()
            
            # 将当前实验数据添加到连续实验数据中
            self.continuous_data['experiment_count'] += 1
            experiment_copy = {
                'experiment_id': self.continuous_data['experiment_count'],
                'start_time': self.current_experiment_data['start_time'],
                'end_time': self.current_experiment_data['end_time'],
                'data': self.current_experiment_data.copy()
            }
            self.continuous_data['experiments'].append(experiment_copy)
        
        logger.info("=== 控制已完全停止 ===\n")

    def update_elapsed_time(self):
        if self.is_running and not self.is_paused:
            self.elapsed_seconds += 1
            minutes = self.elapsed_seconds // 60
            seconds = self.elapsed_seconds % 60
            self.timer_label.setText(f"Elapsed Time: {minutes}:{seconds:02d}")

    def update_status(self):
        """更新状态和图表"""
        current_time = time.time()
        logger.info(f"当前时间: {current_time}")
        if self.pid_controller and self.pid_controller.modbus_sensor:
            # 直接读取传感器数据
            temperatures = {}
            
            # 读取主传感器温度
            if self.main_sensor is not None:
                try:
                    temperature = self.pid_controller.modbus_sensor.read_temperature(self.main_sensor)
                    if temperature is not None:
                        temperatures[self.main_sensor] = temperature
                        logger.debug(f"主传感器 {self.main_sensor} 温度: {temperature}°C")
                except Exception as e:
                    logger.error(f"读取主传感器 {self.main_sensor} 温度失败: {e}")
            
            # 读取其他选中传感器的温度
            for sensor in self.selected_sensors:
                try:
                    temperature = self.pid_controller.modbus_sensor.read_temperature(sensor)
                    if temperature is not None:
                        temperatures[sensor] = temperature
                        logger.debug(f"传感器 {sensor} 温度: {temperature}°C")
                except Exception as e:
                    logger.error(f"读取传感器 {sensor} 温度失败: {e}")
            
            # 更新图表
            self.update_plots()
            
            # 更新其他状态显示
            current_voltage = self.pid_controller.get_current_voltage()
            
            # 打印调试信息
            logger.info("\n=== 状态更新调试信息 ===")
            logger.info(f"所有温度数据: {temperatures}")
            logger.info(f"当前电压: {current_voltage}V")
            logger.info("=== 状态更新完成 ===\n")
            
            # 如果是实际控制模式，执行PID控制
            if self.main_sensor in temperatures:
                current_temp = temperatures[self.main_sensor]
                self.pid_control(current_temp)

    # 修改 update_plots 方法，确保数据同步 2025-05-16 更新 
    def update_plots(self):
        """更新图表显示"""
        if self.pid_controller and self.pid_controller.modbus_sensor:
            # 记录当前时间
            current_time = time.time()
            logger.info(f"\n=== 数据记录时间: {datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')} ===")
            
            # 获取当前时间
            elapsed_time = current_time - self.start_time if hasattr(self, 'start_time') else 0
            
            # 确定当前数据状态
            current_state = 'pause' if self.is_paused else 'control'
            if not hasattr(self, 'warmup_completed'):
                current_state = 'warmup'
            
            # 更新控制数据用于显示
            self.control_data['time'].append(elapsed_time)
            self.control_data['data_states'].append(current_state)
            
            # 同时更新当前实验数据
            self.current_experiment_data['time'].append(elapsed_time)
            self.current_experiment_data['data_states'].append(current_state)
            
            # 更新电压数据
            try:
                voltage_start = time.time()
                current_voltage = self.pid_controller.power_supply.read_voltage()
                voltage_end = time.time()
                logger.info(f"读取电压耗时: {(voltage_end - voltage_start)*1000:.2f}ms")
                if current_voltage is not None:
                    self.control_data['voltage'].append(current_voltage)
                    self.current_experiment_data['voltage'].append(current_voltage)
            except Exception as e:
                logger.error(f"读取电压失败: {e}")
                self.control_data['voltage'].append(None)
                self.current_experiment_data['voltage'].append(None)
            
            # 更新电流数据
            try:
                current_start = time.time()
                current_current = self.pid_controller.power_supply.read_current()
                current_end = time.time()
                logger.info(f"读取电流耗时: {(current_end - current_start)*1000:.2f}ms")
                if current_current is not None:
                    self.control_data['current'].append(current_current)
                    self.current_experiment_data['current'].append(current_current)
            except Exception as e:
                logger.error(f"读取电流失败: {e}")
                self.control_data['current'].append(None)
                self.current_experiment_data['current'].append(None)
            
            # 更新温度数据
            self.temperature_plot.clear()
            colors = ['r', 'g', 'b', 'y', 'c', 'm', 'w', 'k']
            
            # 确保所有传感器数据长度一致
            data_length = len(self.control_data['time'])
            
            # 处理主传感器数据
            if self.main_sensor is not None:
                try:
                    temp_start = time.time()
                    temp = self.pid_controller.modbus_sensor.read_temperature(self.main_sensor)
                    temp_end = time.time()
                    logger.info(f"读取主传感器温度耗时: {(temp_end - temp_start)*1000:.2f}ms")
                    channel_key = f'channel_{self.main_sensor}'
                    
                    # 确保数据结构存在
                    if channel_key not in self.control_data['temperatures']:
                        self.control_data['temperatures'][channel_key] = [None] * (data_length - 1)
                    if channel_key not in self.current_experiment_data['temperatures']:
                        self.current_experiment_data['temperatures'][channel_key] = [None] * (data_length - 1)
                    
                    # 更新数据
                    self.control_data['temperatures'][channel_key].append(temp)
                    self.current_experiment_data['temperatures'][channel_key].append(temp)
                    
                except Exception as e:
                    logger.error(f"读取主传感器温度失败: {e}")
                    if channel_key not in self.control_data['temperatures']:
                        self.control_data['temperatures'][channel_key] = [None] * data_length
                        self.current_experiment_data['temperatures'][channel_key] = [None] * data_length
                    else:
                        self.control_data['temperatures'][channel_key].append(None)
                        self.current_experiment_data['temperatures'][channel_key].append(None)
            
            # 处理其他传感器数据
            for i, sensor in enumerate(self.selected_sensors):
                try:
                    temp_start = time.time()
                    temp = self.pid_controller.modbus_sensor.read_temperature(sensor)
                    temp_end = time.time()
                    logger.info(f"读取传感器 {sensor} 温度耗时: {(temp_end - temp_start)*1000:.2f}ms")
                    channel_key = f'channel_{sensor}'
                    
                    # 确保数据结构存在
                    if channel_key not in self.control_data['temperatures']:
                        self.control_data['temperatures'][channel_key] = [None] * (data_length - 1)
                    if channel_key not in self.current_experiment_data['temperatures']:
                        self.current_experiment_data['temperatures'][channel_key] = [None] * (data_length - 1)
                    
                    # 更新数据
                    self.control_data['temperatures'][channel_key].append(temp)
                    self.current_experiment_data['temperatures'][channel_key].append(temp)
                    
                except Exception as e:
                    logger.error(f"读取传感器 {sensor} 温度失败: {e}")
                    if channel_key not in self.control_data['temperatures']:
                        self.control_data['temperatures'][channel_key] = [None] * data_length
                        self.current_experiment_data['temperatures'][channel_key] = [None] * data_length
                    else:
                        self.control_data['temperatures'][channel_key].append(None)
                        self.current_experiment_data['temperatures'][channel_key].append(None)
            
            # 更新图表显示
            plot_start = time.time()
            self.update_plot_display()
            plot_end = time.time()
            logger.info(f"更新图表耗时: {(plot_end - plot_start)*1000:.2f}ms")
            
            # 记录总耗时
            end_time = time.time()
            logger.info(f"总耗时: {(end_time - current_time)*1000:.2f}ms")
            logger.info("=== 数据记录完成 ===\n")

    def update_plot_display(self):
        """更新图表显示"""
        if self.pid_controller and self.pid_controller.modbus_sensor:
            # 获取当前时间
            current_time = time.time() - self.start_time if hasattr(self, 'start_time') else 0
            
            # 更新电压图表
            self.voltage_plot.clear()
            self.voltage_plot.plot(
                self.control_data['time'], 
                self.control_data['voltage'], 
                pen='r', 
                name='Voltage'
            )
            
            # 更新电流图表
            self.current_plot.clear()
            self.current_plot.plot(
                self.control_data['time'], 
                self.control_data['current'], 
                pen='g', 
                name='Current'
            )
            
            # 更新温度图表
            self.temperature_plot.clear()
            colors = ['r', 'g', 'b', 'y', 'c', 'm', 'w', 'k']
            
            # 首先绘制主传感器的数据（如果有）
            if self.main_sensor is not None:
                try:
                    temp = self.pid_controller.modbus_sensor.read_temperature(self.main_sensor)
                    channel_key = f'channel_{self.main_sensor}'
                    
                    # 确保数据结构存在
                    if channel_key not in self.control_data['temperatures']:
                        self.control_data['temperatures'][channel_key] = [None] * (len(self.control_data['time']) - 1)
                    if channel_key not in self.current_experiment_data['temperatures']:
                        self.current_experiment_data['temperatures'][channel_key] = [None] * (len(self.control_data['time']) - 1)
                    
                    # 更新数据
                    self.control_data['temperatures'][channel_key].append(temp)
                    self.current_experiment_data['temperatures'][channel_key].append(temp)
                    
                    # 绘制主传感器数据
                    valid_data = [(t, v) for t, v in zip(self.control_data['time'], self.control_data['temperatures'][channel_key]) if v is not None]
                    if valid_data:
                        times, temps = zip(*valid_data)
                        self.temperature_plot.plot(
                            times, temps, 
                            pen='r',
                            name=f'Sensor {self.main_sensor} (Main)'
                        )
                        
                except Exception as e:
                    logger.error(f"读取主传感器温度失败: {e}")
                    # 确保数据长度一致
                    channel_key = f'channel_{self.main_sensor}'
                    if channel_key not in self.control_data['temperatures']:
                        self.control_data['temperatures'][channel_key] = [None] * len(self.control_data['time'])
                        self.current_experiment_data['temperatures'][channel_key] = [None] * len(self.control_data['time'])
                    else:
                        self.control_data['temperatures'][channel_key].append(None)
                        self.current_experiment_data['temperatures'][channel_key].append(None)
            
            # 处理其他传感器
            for i, sensor in enumerate(self.selected_sensors):
                try:
                    temp = self.pid_controller.modbus_sensor.read_temperature(sensor)
                    channel_key = f'channel_{sensor}'
                    
                    # 确保数据结构存在
                    if channel_key not in self.control_data['temperatures']:
                        self.control_data['temperatures'][channel_key] = [None] * (len(self.control_data['time']) - 1)
                    if channel_key not in self.current_experiment_data['temperatures']:
                        self.current_experiment_data['temperatures'][channel_key] = [None] * (len(self.control_data['time']) - 1)
                    
                    # 更新数据
                    self.control_data['temperatures'][channel_key].append(temp)
                    self.current_experiment_data['temperatures'][channel_key].append(temp)
                    
                    # 绘制传感器数据
                    valid_data = [(t, v) for t, v in zip(self.control_data['time'], self.control_data['temperatures'][channel_key]) if v is not None]
                    if valid_data:
                        times, temps = zip(*valid_data)
                        color_index = (i + 1) % len(colors)
                        self.temperature_plot.plot(
                            times, temps,
                            pen=colors[color_index], 
                            name=f'Sensor {sensor}'
                        )
                        
                except Exception as e:
                    logger.error(f"读取传感器 {sensor} 温度失败: {e}")
                    # 确保数据长度一致
                    channel_key = f'channel_{sensor}'
                    if channel_key not in self.control_data['temperatures']:
                        self.control_data['temperatures'][channel_key] = [None] * len(self.control_data['time'])
                        self.current_experiment_data['temperatures'][channel_key] = [None] * len(self.control_data['time'])
                    else:
                        self.control_data['temperatures'][channel_key].append(None)
                        self.current_experiment_data['temperatures'][channel_key].append(None)
            
            # 设置图表属性
            self.temperature_plot.addLegend()
            self.temperature_plot.enableAutoRange()
            logger.info("=== 图表更新完成 ===\n")

    def select_save_directory(self):
        """选择数据保存目录"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Save Directory",
            os.path.expanduser("~"),  # 默认从用户主目录开始
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self.save_dir_input.setText(directory)

    def export_data(self):
        """导出数据到Excel文件，分为两个sheet：温度数据和电压电流数据"""
        if not self.pid_controller:
            QMessageBox.warning(self, "警告", "PID控制器未初始化")
            return
            
        # 获取记录的数据
        data = self.pid_controller.get_recorded_data()
        if not data['time']:
            QMessageBox.warning(self, "警告", "没有可导出的数据")
            return
            
        # 创建温度数据字典
        temp_data = {
            'System Time': [datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S') for t in data['system_time']],
            'Elapsed Time (s)': data['time']
        }
        
        # 添加所有选中的传感器温度数据
        for sensor in self.selected_sensors:
            channel_key = f'channel_{sensor}'
            if channel_key in data['temperatures'] and data['temperatures'][channel_key]:
                temp_data[f'Sensor {sensor} Temperature (°C)'] = data['temperatures'][channel_key]
        
        # 创建电压电流数据字典
        power_data = {
            'System Time': [datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S') for t in data['system_time']],
            'Elapsed Time (s)': data['time'],
            'Voltage (V)': data['voltage'],
            'Current (A)': data['current']
        }
        
        # 创建两个DataFrame
        temp_df = pd.DataFrame(temp_data)
        power_df = pd.DataFrame(power_data)
        
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存数据",
            self.save_dir_input.text(),
            "Excel Files (*.xlsx)"
        )
        
        if file_path:
            try:
                # 使用ExcelWriter创建多sheet的Excel文件
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    # 写入温度数据
                    temp_df.to_excel(writer, sheet_name='Temperature Data', index=False)
                    # 写入电压电流数据
                    power_df.to_excel(writer, sheet_name='Power Data', index=False)
                
                QMessageBox.information(self, "成功", "数据已成功保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存数据失败: {str(e)}")

    def enlarge_plot(self, evt, plot_widget, title):
        """双击放大图表"""
        if evt.double():
            # 为每个图表创建唯一的标识符
            window_id = f"{title}_{id(plot_widget)}"
            
            # 如果窗口不存在或已关闭，创建新窗口
            if window_id not in self.enlarged_windows or not self.enlarged_windows[window_id].isVisible():
                # 创建新窗口并设置位置
                window = EnlargedPlotWindow(plot_widget, title)
                # 设置窗口位置，避免重叠
                x = 100 + (self.window_position % 3) * 850  # 每行最多3个窗口
                y = 100 + (self.window_position // 3) * 650  # 每列最多2个窗口
                window.move(x, y)
                self.enlarged_windows[window_id] = window
                self.window_position += 1
                window.show()
            else:
                # 更新已存在的窗口
                self.enlarged_windows[window_id].update_plot(plot_widget)
                self.enlarged_windows[window_id].raise_()

    def show_material_params_dialog(self):
        """显示材料参数对话框"""
        dialog = MaterialParamsDialog(self)
        dialog.exec_()  # 对话框已经处理了保存逻辑

    def save_material_params_to_file(self):
        """保存材料参数到文件"""
        if self.material_params:
            try:
                with open(self.config_file, 'w') as f:
                    json.dump(self.material_params, f, indent=4)
                logger.info(f"材料参数已保存到: {self.config_file}")
            except Exception as e:
                logger.error(f"保存材料参数失败: {e}")

    def load_material_params(self):
        """从文件加载材料参数"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.material_params = json.load(f)
                    logger.info(f"已加载{len(self.material_params)}组材料参数")
            else:
                self.material_params = {}
                logger.info("材料参数文件不存在，使用空字典")
        except Exception as e:
            logger.error(f"加载材料参数失败: {e}")
            self.material_params = {}

    def apply_material_params(self, material_name, params):
        """将材料参数应用到控制参数输入框"""
        if not params:
            return
            
        # 设置初始电压
        if "initial_voltage" in params:
            self.initial_voltage_input.setText(str(params["initial_voltage"]))
        
        # The maximum voltage
        if "max_voltage" in params:
            self.max_voltage_input.setText(str(params["max_voltage"]))
        
        # The target temperature
        if "target_temp" in params:
            self.setpoint_input.setText(str(params["target_temp"]))
        
        # The warm-up time
        if "warmup_time" in params:
            self.warmup_input.setText(str(params["warmup_time"]))
        
        # 设置PID参数
        if "kp" in params:
            self.kp_input.setText(str(params["kp"]))
        if "ki" in params:
            self.ki_input.setText(str(params["ki"]))
        if "kd" in params:
            self.kd_input.setText(str(params["kd"]))
        
        QMessageBox.information(
            self, 
            "Material Parameters Loaded", 
            f"Parameters for '{material_name}' have been applied to control settings"
        )

    def handle_legend_click(self, evt):
        """处理图例点击事件"""
        if evt.button() == Qt.LeftButton:
            # 获取点击事件发生的场景
            scene = evt.scene()
            if scene:
                # 获取场景中的视图
                view = scene.views()[0]
                if view:
                    # 获取视图中的plot对象
                    plot = view.parent()
                    if plot:
                        plot.setTitle("点击图例")
                        plot.repaint()

    def start_temperature_test(self):
        """开始温度测试"""
        # 获取当前选择的串口
        port = self.temp_sensor_port_combo.currentText()
        if not port:
            QMessageBox.warning(self, "警告", "请先选择温度传感器串口")
            return
            
        # 检查是否已连接传感器
        if not self.pid_controller.modbus_sensor:
            logger.info("正在连接温度传感器...")
            if not self.pid_controller.connect_sensor(port):
                QMessageBox.warning(self, "警告", "连接温度传感器失败，请检查串口连接")
                return
                
        # 检查传感器是否已连接
        if not self.pid_controller.modbus_sensor.is_connected():
            logger.info("温度传感器未连接，尝试重新连接...")
            if not self.pid_controller.connect_sensor(port):
                QMessageBox.warning(self, "警告", "重新连接温度传感器失败，请检查串口连接")
                return
            
        # 检查是否选择了传感器
        if not self.pid_controller.selected_sensors and self.pid_controller.main_sensor is None:
            QMessageBox.warning(self, "警告", "请先选择要测试的传感器")
            return

        # 创建测试数据存储
        self.test_data = {
            'time': [],
            'temperatures': {}
        }

        # 初始化所有传感器的温度数据队列
        if self.pid_controller.main_sensor is not None:
            self.test_data['temperatures'][f'channel_{self.pid_controller.main_sensor}'] = []
        for sensor in self.pid_controller.selected_sensors:
            self.test_data['temperatures'][f'channel_{sensor}'] = []

        # 开始测试
        self.test_start_time = time.time()
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.update_test_data)
        self.test_timer.start(1000)  # 每秒更新一次

        # 更新按钮状态
        self.start_test_button.setEnabled(False)
        self.stop_test_button.setEnabled(True)
        self.test_status_label.setText("Test Status: Running")

    def update_test_data(self):
        """更新测试数据"""
        elapsed_time = time.time() - self.test_start_time

        # 记录时间
        self.test_data['time'].append(elapsed_time)

        # 读取主传感器的温度（如果存在）
        if self.pid_controller.main_sensor is not None:
            try:
                temperature = self.pid_controller.modbus_sensor.read_temperature(self.pid_controller.main_sensor)
                if temperature is not None:
                    channel_key = f'channel_{self.pid_controller.main_sensor}'
                    if channel_key not in self.test_data['temperatures']:
                        self.test_data['temperatures'][channel_key] = []
                    self.test_data['temperatures'][channel_key].append(temperature)
                    logger.debug(f"主传感器 {self.pid_controller.main_sensor} 温度: {temperature}°C")
            except Exception as e:
                logger.error(f"读取主传感器 {self.pid_controller.main_sensor} 温度失败: {e}")

        # 读取所有选中传感器的温度
        for sensor in self.pid_controller.selected_sensors:
            try:
                temperature = self.pid_controller.modbus_sensor.read_temperature(sensor)
                if temperature is not None:
                    channel_key = f'channel_{sensor}'
                    if channel_key not in self.test_data['temperatures']:
                        self.test_data['temperatures'][channel_key] = []
                    self.test_data['temperatures'][channel_key].append(temperature)
                    logger.debug(f"传感器 {sensor} 温度: {temperature}°C")
            except Exception as e:
                logger.error(f"读取传感器 {sensor} 温度失败: {e}")

        # 更新主窗口的温度图表
        self.update_test_plots(self.test_data)

    def update_test_plots(self, test_data):
        """更新测试图表"""
        if not self.temperature_plot:
            return
            
        self.temperature_plot.clear()
        colors = ['r', 'g', 'b', 'y', 'c', 'm']  # 为不同传感器准备不同颜色
        
        # 首先绘制主传感器的数据（如果有）
        if self.pid_controller.main_sensor is not None:
            channel_key = f'channel_{self.pid_controller.main_sensor}'
            if channel_key in test_data['temperatures'] and test_data['temperatures'][channel_key]:
                self.temperature_plot.plot(
                    test_data['time'], 
                    test_data['temperatures'][channel_key], 
                    pen='r', 
                    name=f'主传感器 {self.pid_controller.main_sensor}'
                )
        
        # 然后绘制其他传感器的数据
        for i, (channel, temps) in enumerate(test_data['temperatures'].items()):
            sensor_num = int(channel.split('_')[1])
            # 跳过主传感器，因为已经绘制过了
            if sensor_num == self.pid_controller.main_sensor:
                continue
            if temps:
                color = colors[i % len(colors)]
                self.temperature_plot.plot(
                    test_data['time'], 
                    temps, 
                    pen=color, 
                    name=f'传感器 {sensor_num}'
                )
        
        # 添加图例
        self.temperature_plot.addLegend()
        
        # 设置图表属性
        self.temperature_plot.setLabel('left', '温度 (°C)')
        self.temperature_plot.setLabel('bottom', '时间 (s)')
        self.temperature_plot.setTitle('温度传感器测试')
        self.temperature_plot.showGrid(True, True)
        self.temperature_plot.enableAutoRange()

    def stop_temperature_test(self):
        """停止温度测试并保存数据"""
        if hasattr(self, 'test_timer'):
            self.test_timer.stop()
            logger.info("温度传感器测试完成")
            
            # 更新按钮状态
            self.start_test_button.setEnabled(True)
            self.stop_test_button.setEnabled(False)
            self.test_status_label.setText("Test Status: Completed")
            
            # 保存测试数据
            self.save_test_data()

    def save_test_data(self):
        """保存测试数据"""
        if not self.test_data['time']:
            QMessageBox.warning(self, "警告", "没有测试数据可保存")
            return

        # 创建DataFrame
        df = pd.DataFrame()
        df['Time (s)'] = self.test_data['time']
        
        # 添加所有传感器的温度数据
        for channel, temps in self.test_data['temperatures'].items():
            sensor_num = int(channel.split('_')[1])
            df[f'Sensor {sensor_num} Temperature (°C)'] = temps

        # 获取保存目录
        save_dir = self.save_dir_input.text()
        if not save_dir:
            QMessageBox.warning(self, "警告", "请先设置数据保存目录")
            return

        # 生成文件名
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"temperature_test_{current_time}.xlsx"

        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存测试数据",
            os.path.join(save_dir, default_filename),
            "Excel Files (*.xlsx)"
        )

        if file_path:
            try:
                df.to_excel(file_path, index=False)
                QMessageBox.information(self, "成功", "测试数据已保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存测试数据失败: {str(e)}")

    def test_power_supply(self):
        """测试电源发生器"""
        if not self.pid_controller.power_supply:
            QMessageBox.warning(self, "警告", "请先连接电源发生器")
            return

        # 创建测试数据存储
        test_data = {
            'time': [],
            'voltage': [],
            'current': []
        }

        # 创建测试窗口
        test_window = QDialog(self)
        test_window.setWindowTitle("电源发生器测试")
        test_window.setModal(True)
        test_window.setMinimumSize(800, 600)

        # 创建布局
        layout = QVBoxLayout(test_window)

        # 创建电压图表
        voltage_plot = pg.PlotWidget()
        voltage_plot.setBackground('w')
        voltage_plot.setLabel('left', '电压 (V)')
        voltage_plot.setLabel('bottom', '时间 (s)')
        voltage_plot.addLegend()
        layout.addWidget(voltage_plot)

        # 创建电流图表
        current_plot = pg.PlotWidget()
        current_plot.setBackground('w')
        current_plot.setLabel('left', '电流 (A)')
        current_plot.setLabel('bottom', '时间 (s)')
        current_plot.addLegend()
        layout.addWidget(current_plot)

        # 创建状态标签
        status_label = QLabel("测试中...")
        layout.addWidget(status_label)

        # 创建按钮
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存数据")
        close_button = QPushButton("关闭")
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        # 连接信号
        save_button.clicked.connect(lambda: self.save_power_test_data(test_data))
        close_button.clicked.connect(test_window.close)

        # 显示窗口
        test_window.show()

        # 开始测试
        start_time = time.time()
        timer = QTimer()
        timer.timeout.connect(lambda: self.update_power_test_data(
            self.pid_controller.power_supply, test_data, start_time, timer))
        timer.start(1000)  # 每秒更新一次

    def update_power_test_data(self, power_supply, test_data, start_time, timer, duration=60):
        """更新电源测试数据"""
        elapsed_time = time.time() - start_time
        if elapsed_time >= duration:
            timer.stop()
            return

        # 记录时间
        test_data['time'].append(elapsed_time)

        # 读取电压和电流
        try:
            voltage = power_supply.read_voltage()
            if voltage is not None:
                test_data['voltage'].append(voltage)

            current = power_supply.read_current()
            if current is not None:
                test_data['current'].append(current)
        except Exception as e:
            logger.error(f"读取电压或电流失败: {e}")

        # 更新图表
        self.update_power_test_plots(test_data)

    def update_power_test_plots(self, test_data):
        """更新电源测试图表"""
        plot_widgets = self.findChildren(pg.PlotWidget)
        if len(plot_widgets) < 2:
            return

        # 更新电压图表
        plot_widgets[0].clear()
        if test_data['voltage']:
            plot_widgets[0].plot(test_data['time'], test_data['voltage'], name='电压')

        # 更新电流图表
        plot_widgets[1].clear()
        if test_data['current']:
            plot_widgets[1].plot(test_data['time'], test_data['current'], name='电流')

    def save_power_test_data(self, test_data):
        """保存电源测试数据"""
        if not test_data['time']:
            QMessageBox.warning(self, "警告", "没有测试数据可保存")
            return

        # 创建DataFrame
        df = pd.DataFrame()
        df['time'] = test_data['time']
        df['voltage'] = test_data['voltage']
        df['current'] = test_data['current']

        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存测试数据", "", "Excel Files (*.xlsx)")
        if file_path:
            try:
                df.to_excel(file_path, index=False)
                QMessageBox.information(self, "成功", "测试数据已保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存测试数据失败: {e}")

    def control_finished(self):
        """控制线程完成时的处理"""
        self.is_running = False
        self.is_paused = False
        self.status_label.setText("Status: Stopped")
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)

    def pid_control(self, current_temp):
        """执行PID控制"""
        if self.pid_controller:
            try:
                # 执行PID控制
                self.pid_controller.update(current_temp)
                logger.debug(f"PID控制执行成功，当前温度: {current_temp}°C")
            except Exception as e:
                logger.error(f"PID控制执行失败: {e}")

    def export_single_experiment(self):
        """导出当前实验的数据"""
        # 检查是否有连续实验数据
        if self.continuous_data['experiments']:
            # 创建实验选择对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("选择要导出的实验")
            layout = QVBoxLayout()
            
            # 创建实验选择列表
            experiment_list = QListWidget()
            for experiment in self.continuous_data['experiments']:
                exp_id = experiment['experiment_id']
                start_time = datetime.fromtimestamp(experiment['start_time']).strftime('%Y-%m-%d %H:%M:%S')
                item = QListWidgetItem(f"实验 {exp_id} (开始时间: {start_time})")
                item.setData(Qt.UserRole, exp_id)
                experiment_list.addItem(item)
            
            layout.addWidget(QLabel("选择要导出的实验:"))
            layout.addWidget(experiment_list)
            
            # 添加按钮
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.setLayout(layout)
            
            if dialog.exec_() == QDialog.Accepted:
                selected_items = experiment_list.selectedItems()
                if selected_items:
                    experiment_id = selected_items[0].data(Qt.UserRole)
                    # 从连续实验数据中找到选中的实验
                    selected_experiment = None
                    for experiment in self.continuous_data['experiments']:
                        if experiment['experiment_id'] == experiment_id:
                            selected_experiment = experiment
                            break
                    
                    if selected_experiment:
                        exp_data = selected_experiment['data']
                    else:
                        QMessageBox.warning(self, "警告", f"未找到ID为{experiment_id}的实验数据")
                        return
                else:
                    return
            else:
                return
        else:
            # 如果没有连续实验数据，使用当前实验数据
            if not self.current_experiment_data['time']:
                QMessageBox.warning(self, "警告", "没有当前实验数据可导出")
                return
            exp_data = self.current_experiment_data
        
        # 创建温度数据字典
        temp_data = {
            'Time (s)': exp_data['time'],
            'Data State': exp_data['data_states']
        }
        
        # 添加系统时间
        if exp_data['start_time']:
            system_times = [
                datetime.fromtimestamp(exp_data['start_time'] + t).strftime('%Y-%m-%d %H:%M:%S')
                for t in exp_data['time']
            ]
            temp_data['System Time'] = system_times
        
        # 添加温度数据
        if self.main_sensor is not None:
            channel_key = f'channel_{self.main_sensor}'
            if channel_key in exp_data['temperatures']:
                temp_data[f'Sensor {self.main_sensor} Temperature (°C) [Main]'] = exp_data['temperatures'][channel_key]
        
        for sensor in self.selected_sensors:
            channel_key = f'channel_{sensor}'
            if channel_key in exp_data['temperatures']:
                temp_data[f'Sensor {sensor} Temperature (°C)'] = exp_data['temperatures'][channel_key]
        
        # 创建电压电流数据字典
        power_data = {
            'Time (s)': exp_data['time'],
            'Data State': exp_data['data_states'],
            'Voltage (V)': exp_data['voltage'],
            'Current (A)': exp_data['current']
        }
        
        if exp_data['start_time']:
            power_data['System Time'] = system_times
        
        # 创建DataFrame
        temp_df = pd.DataFrame(temp_data)
        power_df = pd.DataFrame(power_data)
        
        # 选择保存路径
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"PID_Experiment_{current_time}.xlsx"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存实验数据",
            os.path.join(self.save_dir_input.text(), default_filename),
            "Excel Files (*.xlsx)"
        )
        
        if file_path:
            try:
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    temp_df.to_excel(writer, sheet_name='Temperature Data', index=False)
                    power_df.to_excel(writer, sheet_name='Power Data', index=False)
                    
                    # 添加实验阶段统计信息
                    state_stats = {
                        'Phase': ['Warm-up', 'PID Control', 'Pause'],
                        'Duration (s)': [
                            sum(1 for x in exp_data['data_states'] if x == 'warmup'),
                            sum(1 for x in exp_data['data_states'] if x == 'control'),
                            sum(1 for x in exp_data['data_states'] if x == 'pause')
                        ]
                    }
                    stats_df = pd.DataFrame(state_stats)
                    stats_df.to_excel(writer, sheet_name='Experiment Phases', index=False)
                    
                QMessageBox.information(self, "成功", "实验数据已成功保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存数据失败: {str(e)}")

    def export_continuous_experiments(self):
        """导出所有连续实验的数据"""
        if not self.continuous_data['experiments']:
            QMessageBox.warning(self, "警告", "没有连续实验数据可导出")
            return
        
        # 合并所有实验数据
        combined_temp_data = {'Time (s)': [], 'System Time': [], 'Experiment ID': []}
        combined_power_data = {'Time (s)': [], 'System Time': [], 'Experiment ID': []}
        
        # 初始化传感器数据列
        if self.main_sensor is not None:
            combined_temp_data[f'Sensor {self.main_sensor} Temperature (°C) [Main]'] = []
        for sensor in self.selected_sensors:
            combined_temp_data[f'Sensor {sensor} Temperature (°C)'] = []
        
        combined_power_data['Voltage (V)'] = []
        combined_power_data['Current (A)'] = []
        
        # 合并每个实验的数据
        for experiment in self.continuous_data['experiments']:
            exp_data = experiment['data']
            exp_id = experiment['experiment_id']
            start_time = experiment['start_time']
            
            for i, elapsed_time in enumerate(exp_data['time']):
                # 添加基本信息
                combined_temp_data['Time (s)'].append(elapsed_time)
                combined_power_data['Time (s)'].append(elapsed_time)
                
                combined_temp_data['Experiment ID'].append(exp_id)
                combined_power_data['Experiment ID'].append(exp_id)
                
                # 添加系统时间
                system_time = datetime.fromtimestamp(start_time + elapsed_time).strftime('%Y-%m-%d %H:%M:%S')
                combined_temp_data['System Time'].append(system_time)
                combined_power_data['System Time'].append(system_time)
                
                # 添加温度数据
                if self.main_sensor is not None:
                    channel_key = f'channel_{self.main_sensor}'
                    if channel_key in exp_data['temperatures'] and i < len(exp_data['temperatures'][channel_key]):
                        combined_temp_data[f'Sensor {self.main_sensor} Temperature (°C) [Main]'].append(
                            exp_data['temperatures'][channel_key][i]
                        )
                    else:
                        combined_temp_data[f'Sensor {self.main_sensor} Temperature (°C) [Main]'].append(None)
                
                for sensor in self.selected_sensors:
                    channel_key = f'channel_{sensor}'
                    if channel_key in exp_data['temperatures'] and i < len(exp_data['temperatures'][channel_key]):
                        combined_temp_data[f'Sensor {sensor} Temperature (°C)'].append(
                            exp_data['temperatures'][channel_key][i]
                        )
                    else:
                        combined_temp_data[f'Sensor {sensor} Temperature (°C)'].append(None)
                
                # 添加电压电流数据
                if i < len(exp_data['voltage']):
                    combined_power_data['Voltage (V)'].append(exp_data['voltage'][i])
                else:
                    combined_power_data['Voltage (V)'].append(None)
                    
                if i < len(exp_data['current']):
                    combined_power_data['Current (A)'].append(exp_data['current'][i])
                else:
                    combined_power_data['Current (A)'].append(None)
        
        # 创建DataFrame
        temp_df = pd.DataFrame(combined_temp_data)
        power_df = pd.DataFrame(combined_power_data)
        
        # 选择保存路径
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"PID_Continuous_Experiments_{current_time}.xlsx"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存连续实验数据",
            os.path.join(self.save_dir_input.text(), default_filename),
            "Excel Files (*.xlsx)"
        )
        
        if file_path:
            try:
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    temp_df.to_excel(writer, sheet_name='Temperature Data', index=False)
                    power_df.to_excel(writer, sheet_name='Power Data', index=False)
                    
                    # 添加实验摘要sheet
                    summary_data = {
                        'Experiment ID': [],
                        'Start Time': [],
                        'End Time': [],
                        'Duration (s)': []
                    }
                    
                    for experiment in self.continuous_data['experiments']:
                        summary_data['Experiment ID'].append(experiment['experiment_id'])
                        summary_data['Start Time'].append(
                            datetime.fromtimestamp(experiment['start_time']).strftime('%Y-%m-%d %H:%M:%S')
                        )
                        summary_data['End Time'].append(
                            datetime.fromtimestamp(experiment['end_time']).strftime('%Y-%m-%d %H:%M:%S')
                        )
                        summary_data['Duration (s)'].append(
                            experiment['end_time'] - experiment['start_time']
                        )
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Experiment Summary', index=False)
                    
                QMessageBox.information(self, "成功", f"连续实验数据已成功保存（共{self.continuous_data['experiment_count']}次实验）")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存数据失败: {str(e)}")

    def clear_continuous_data(self):
        """清除连续实验数据"""
        self.continuous_data = {
            'experiments': [],
            'experiment_count': 0
        }
        QMessageBox.information(self, "信息", "连续实验数据已清除")

    def show_log_file_path(self):
        """显示日志文件路径"""
        log_file = logger.get_log_file_path()
        QMessageBox.information(
            self,
            "Log File Location",
            f"Log file is located at:\n{log_file}\n\nYou can find detailed logs and error messages in this file."
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PIDSystemUI()
    window.show()
    sys.exit(app.exec_())