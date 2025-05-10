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
        print("控制线程开始运行")
        while self.is_running:
            if not self.is_paused:
                try:
                    # 读取当前温度
                    if self.pid_controller.modbus_sensor and self.pid_controller.main_sensor:
                        current_temp = self.pid_controller.modbus_sensor.read_temperature(self.pid_controller.main_sensor)
                        if current_temp is not None:
                            print(f"\n=== PID控制循环 ===")
                            print(f"读取到主传感器温度: {current_temp}°C")
                            print(f"PID控制器状态: running={self.pid_controller.is_running}, paused={self.pid_controller.is_paused}")
                            # 执行PID控制
                            self.pid_controller.update(current_temp)
                            print("=== PID控制循环完成 ===\n")
                        else:
                            print("无法读取主传感器温度")
                    else:
                        print("温度传感器或主传感器未设置")
                except Exception as e:
                    print(f"PID控制执行失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("控制已暂停")
            self.msleep(self.pid_controller.sampling_rate)  # 使用PID控制器的采样率
        print("控制线程停止运行")
        self.finished.emit()
        
    def stop(self):
        """停止控制线程"""
        print("正在停止控制线程...")
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
                        # 保存曲线引用
                        self.curves[name] = new_curve
                except Exception as e:
                    print(f"Error copying curve data: {e}")
        
        # 添加图例
        self.plot.addLegend()
        
        # 设置交互功能
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.enableAutoRange()
        
        layout.addWidget(self.plot)
        
        # 添加关闭按钮
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def update_plot(self, plot_widget):
        """更新放大窗口中的图表数据"""
        # 清除现有曲线
        self.plot.clear()
        self.curves.clear()
        
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
                        # 保存曲线引用
                        self.curves[name] = new_curve
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
        self.setWindowTitle("material parameters management")
        self.setGeometry(200, 200, 400, 300)
        
        layout = QVBoxLayout()
        
        # 材料名称输入
        self.material_name = QLineEdit()
        self.material_name.setPlaceholderText("material name")
        layout.addWidget(QLabel("material name:"))
        layout.addWidget(self.material_name)
        
        # 参数输入
        self.initial_voltage = QDoubleSpinBox()
        self.initial_voltage.setRange(0, 30)
        self.initial_voltage.setSingleStep(0.1)
        layout.addWidget(QLabel("initial voltage (V):"))
        layout.addWidget(self.initial_voltage)
        
        self.kp = QDoubleSpinBox()
        self.kp.setRange(0, 100)
        self.kp.setSingleStep(0.1)
        layout.addWidget(QLabel("Kp:"))
        layout.addWidget(self.kp)
        
        self.ki = QDoubleSpinBox()
        self.ki.setRange(0, 100)
        self.ki.setSingleStep(0.1)
        layout.addWidget(QLabel("Ki:"))
        layout.addWidget(self.ki)
        
        self.kd = QDoubleSpinBox()
        self.kd.setRange(0, 100)
        self.kd.setSingleStep(0.1)
        layout.addWidget(QLabel("Kd:"))
        layout.addWidget(self.kd)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("save parameters")
        self.load_button = QPushButton("load parameters")
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

class PIDSystemUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PID Temperature Control System")
        self.setGeometry(100, 100, 1200, 800)
        
        # 获取配置目录
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
            'current': []
        }
        
        self.init_ui()
        self.material_params = {}  # 存储材料参数
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

        # 电源测试按钮
        self.power_test_button = QPushButton("Test Power Supply")
        self.power_test_button.clicked.connect(self.test_power_supply)
        self.right_layout.addWidget(self.power_test_button)

        # 电源测试状态显示
        self.power_test_status_label = QLabel("Power Test Status: Not Started")
        self.right_layout.addWidget(self.power_test_status_label)

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
        self.save_dir_layout = QHBoxLayout()
        self.save_dir_label = QLabel("Save Directory:")
        self.save_dir_input = QLineEdit()
        self.save_dir_input.setReadOnly(True)
        self.save_dir_button = QPushButton("Browse")
        self.save_dir_button.clicked.connect(self.select_save_directory)
        self.save_dir_layout.addWidget(self.save_dir_label)
        self.save_dir_layout.addWidget(self.save_dir_input)
        self.save_dir_layout.addWidget(self.save_dir_button)
        self.right_layout.addLayout(self.save_dir_layout)

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
        self.export_button = QPushButton("Export Data")
        self.export_button.clicked.connect(self.export_data)
        self.control_buttons_layout.addWidget(self.export_button)

        self.right_layout.addLayout(self.control_buttons_layout)

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
        
        # 设置PID参数
        self.pid_controller.set_pid_params(kp, ki, kd)
        self.pid_controller.set_sampling_rate(sampling_rate)
        self.pid_controller.set_initial_voltage(initial_voltage)
        self.pid_controller.set_target_temp(target_temp)
        self.pid_controller.set_duration(duration)
        self.pid_controller.set_temp_error(temp_error)
        
        # 连接温度传感器
        temp_sensor_port = self.temp_sensor_port_combo.currentText()
        if not self.pid_controller.connect_sensor(temp_sensor_port):
            QMessageBox.warning(self, "警告", "连接温度传感器失败")
            return
            
        # 连接电源发生器
        try:
            power_supply_port = self.power_supply_port_combo.currentText()
            if not self.pid_controller.connect_power_supply(power_supply_port):
                QMessageBox.warning(self, "警告", "连接电源发生器失败")
                return
        except Exception as e:
            QMessageBox.warning(self, "错误", f"连接电源发生器时出错: {str(e)}")
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
        
        # 清空之前的数据
        self.control_data = {
            'time': [],
            'temperatures': {},
            'voltage': [],
            'current': []
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
        print("\n=== 开始停止控制 ===")
        
        # 立即停止所有定时器
        if hasattr(self, 'timer'):
            self.timer.stop()
            print("已停止状态更新定时器")
        
        if hasattr(self, 'elapsed_timer'):
            self.elapsed_timer.stop()
            print("已停止计时器")
        
        # 立即设置状态
        self.is_running = False
        self.is_paused = False
        self.status_label.setText("Status: Stopping...")
        
        # 立即停止PID控制器
        if self.pid_controller:
            try:
                print("正在停止PID控制器...")
                # 先关闭电源输出
                if self.pid_controller.power_supply:
                    try:
                        self.pid_controller.power_supply.off_output()
                        print("已关闭电源输出")
                    except Exception as e:
                        print(f"关闭电源输出时发生错误: {e}")
                
                # 停止PID控制
                self.pid_controller.stop()
                print("PID控制器已停止")
            except Exception as e:
                print(f"停止PID控制器时发生错误: {e}")
        
        # 强制停止控制线程
        if hasattr(self, 'control_thread') and self.control_thread.isRunning():
            print("正在停止控制线程...")
            try:
                # 先尝试正常停止
                self.control_thread.stop()
                self.control_thread.wait(1000)  # 等待1秒
                
                # 如果线程还在运行，强制终止
                if self.control_thread.isRunning():
                    print("控制线程未响应，强制终止...")
                    self.control_thread.terminate()
                    self.control_thread.wait(1000)  # 再等待1秒
                    
                    # 如果还是无法停止，使用更强制的方式
                    if self.control_thread.isRunning():
                        print("警告：控制线程无法正常停止，使用强制方式")
                        self.control_thread.quit()
            except Exception as e:
                print(f"停止控制线程时发生错误: {e}")
        
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
            'current': []
        }
        
        print("=== 控制已完全停止 ===\n")

    def update_elapsed_time(self):
        if self.is_running and not self.is_paused:
            self.elapsed_seconds += 1
            minutes = self.elapsed_seconds // 60
            seconds = self.elapsed_seconds % 60
            self.timer_label.setText(f"Elapsed Time: {minutes}:{seconds:02d}")

    def update_status(self):
        """更新状态和图表"""
        if self.pid_controller and self.pid_controller.modbus_sensor:
            # 直接读取传感器数据
            temperatures = {}
            
            # 读取主传感器温度
            if self.main_sensor is not None:
                try:
                    temperature = self.pid_controller.modbus_sensor.read_temperature(self.main_sensor)
                    if temperature is not None:
                        temperatures[self.main_sensor] = temperature
                        print(f"主传感器 {self.main_sensor} 温度: {temperature}°C")
                except Exception as e:
                    print(f"读取主传感器 {self.main_sensor} 温度失败: {e}")
            
            # 读取其他选中传感器的温度
            for sensor in self.selected_sensors:
                try:
                    temperature = self.pid_controller.modbus_sensor.read_temperature(sensor)
                    if temperature is not None:
                        temperatures[sensor] = temperature
                        print(f"传感器 {sensor} 温度: {temperature}°C")
                except Exception as e:
                    print(f"读取传感器 {sensor} 温度失败: {e}")
            
            # 更新图表
            self.update_plots()
            
            # 更新其他状态显示
            current_voltage = self.pid_controller.get_current_voltage()
            
            # 打印调试信息
            print("\n=== 状态更新调试信息 ===")
            print(f"所有温度数据: {temperatures}")
            print(f"当前电压: {current_voltage}V")
            print("=== 状态更新完成 ===\n")
            
            # 如果是实际控制模式，执行PID控制
            if self.main_sensor in temperatures:
                current_temp = temperatures[self.main_sensor]
                self.pid_control(current_temp)

    def update_plots(self):
        """更新图表显示"""
        if self.pid_controller and self.pid_controller.modbus_sensor:
            # 获取当前时间
            current_time = time.time() - self.start_time if hasattr(self, 'start_time') else 0
            
            # 更新电压图表
            self.voltage_plot.clear()
            try:
                current_voltage = self.pid_controller.power_supply.read_voltage()
                if current_voltage is not None:
                    self.control_data['voltage'].append(current_voltage)
                    self.control_data['time'].append(current_time)
                    # 确保数组长度匹配
                    if len(self.control_data['time']) == len(self.control_data['voltage']):
                        self.voltage_plot.plot(
                            self.control_data['time'], 
                            self.control_data['voltage'], 
                            pen='r', 
                            name='Voltage'
                        )
                    self.voltage_plot.setYRange(0, 30)  # 设置Y轴范围
                    self.voltage_plot.enableAutoRange()
                    self.voltage_plot.setMouseEnabled(x=True, y=True)
                    self.voltage_plot.show()
                    self.voltage_plot.update()
            except Exception as e:
                print(f"读取电压失败: {e}")
            
            # 更新电流图表
            self.current_plot.clear()
            try:
                current_current = self.pid_controller.power_supply.read_current()
                if current_current is not None:
                    self.control_data['current'].append(current_current)
                    # 确保数组长度匹配
                    if len(self.control_data['time']) == len(self.control_data['current']):
                        self.current_plot.plot(
                            self.control_data['time'], 
                            self.control_data['current'], 
                            pen='g', 
                            name='Current'
                        )
                    self.current_plot.setYRange(0, 5)  # 设置Y轴范围
                    self.current_plot.enableAutoRange()
                    self.current_plot.setMouseEnabled(x=True, y=True)
                    self.current_plot.show()
                    self.current_plot.update()
            except Exception as e:
                print(f"读取电流失败: {e}")
            
            # 更新温度图表
            self.temperature_plot.clear()
            
            # 定义颜色列表
            colors = ['r', 'g', 'b', 'y', 'c', 'm', 'w', 'k']
            
            # 首先绘制主传感器的数据（如果有）
            if self.main_sensor is not None:
                try:
                    temp = self.pid_controller.modbus_sensor.read_temperature(self.main_sensor)
                    if temp is not None:
                        channel_key = f'channel_{self.main_sensor}'
                        if channel_key not in self.control_data['temperatures']:
                            self.control_data['temperatures'][channel_key] = []
                        
                        # 确保主传感器的数据长度与时间数据长度匹配
                        while len(self.control_data['temperatures'][channel_key]) < len(self.control_data['time']):
                            self.control_data['temperatures'][channel_key].append(np.nan)
                        
                        # 更新最新的温度值
                        self.control_data['temperatures'][channel_key][-1] = temp
                        
                        # 绘制主传感器数据
                        self.temperature_plot.plot(
                            self.control_data['time'], 
                            self.control_data['temperatures'][channel_key], 
                            pen='r',  # 主传感器使用红色
                            name=f'Sensor {self.main_sensor} (Main)'
                        )
                        print(f"主传感器 {self.main_sensor} 温度: {temp}°C")
                except Exception as e:
                    print(f"读取主传感器温度失败: {e}")
            
            # 绘制其他传感器的数据，使用不同的颜色
            for i, sensor in enumerate(self.selected_sensors):
                try:
                    temp = self.pid_controller.modbus_sensor.read_temperature(sensor)
                    if temp is not None:
                        channel_key = f'channel_{sensor}'
                        if channel_key not in self.control_data['temperatures']:
                            self.control_data['temperatures'][channel_key] = []
                        
                        # 确保其他传感器的数据长度与时间数据长度匹配
                        while len(self.control_data['temperatures'][channel_key]) < len(self.control_data['time']):
                            self.control_data['temperatures'][channel_key].append(np.nan)
                        
                        # 更新最新的温度值
                        self.control_data['temperatures'][channel_key][-1] = temp
                        
                        # 绘制其他传感器数据
                        color_index = (i + 1) % len(colors)  # 从第二个颜色开始，跳过红色（主传感器用）
                        self.temperature_plot.plot(
                            self.control_data['time'], 
                            self.control_data['temperatures'][channel_key], 
                            pen=colors[color_index], 
                            name=f'Sensor {sensor}'
                        )
                        print(f"传感器 {sensor} 温度: {temp}°C")
                except Exception as e:
                    print(f"读取传感器 {sensor} 温度失败: {e}")
            
            # 设置温度图表属性
            self.temperature_plot.setYRange(0, 100)  # 设置Y轴范围
            self.temperature_plot.enableAutoRange()
            self.temperature_plot.setMouseEnabled(x=True, y=True)
            self.temperature_plot.show()
            self.temperature_plot.update()
            self.temperature_plot.addLegend()
            
            print("=== 图表更新完成 ===\n")

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
        if dialog.exec_() == QDialog.Accepted:
            self.save_material_params(dialog)

    def save_material_params(self, dialog):
        """保存材料参数"""
        params = dialog.get_params()
        self.material_params = params
        self.save_material_params_to_file()

    def load_material_params_dialog(self, dialog):
        """加载材料参数到对话框"""
        if self.material_params:
            dialog.set_params(self.material_params)

    def save_material_params_to_file(self):
        """保存材料参数到文件"""
        if self.material_params:
            with open(self.config_file, 'w') as f:
                json.dump(self.material_params, f, indent=4)  # 使用indent使文件更易读

    def load_material_params(self):
        """从文件加载材料参数"""
        try:
            with open(self.config_file, 'r') as f:
                self.material_params = json.load(f)
        except FileNotFoundError:
            self.material_params = None

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
            print("正在连接温度传感器...")
            if not self.pid_controller.connect_sensor(port):
                QMessageBox.warning(self, "警告", "连接温度传感器失败，请检查串口连接")
                return
                
        # 检查传感器是否已连接
        if not self.pid_controller.modbus_sensor.is_connected():
            print("温度传感器未连接，尝试重新连接...")
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
                    print(f"主传感器 {self.pid_controller.main_sensor} 温度: {temperature}°C")
            except Exception as e:
                print(f"读取主传感器 {self.pid_controller.main_sensor} 温度失败: {e}")

        # 读取所有选中传感器的温度
        for sensor in self.pid_controller.selected_sensors:
            try:
                temperature = self.pid_controller.modbus_sensor.read_temperature(sensor)
                if temperature is not None:
                    channel_key = f'channel_{sensor}'
                    if channel_key not in self.test_data['temperatures']:
                        self.test_data['temperatures'][channel_key] = []
                    self.test_data['temperatures'][channel_key].append(temperature)
                    print(f"传感器 {sensor} 温度: {temperature}°C")
            except Exception as e:
                print(f"读取传感器 {sensor} 温度失败: {e}")

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
            print("温度传感器测试完成")
            
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
        default_path = os.path.join(save_dir, default_filename)

        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存测试数据",
            default_path,
            "Excel Files (*.xlsx)"
        )

        if file_path:
            try:
                df.to_excel(file_path, index=False)
                QMessageBox.information(self, "成功", "测试数据已保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存测试数据失败: {e}")

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
            print(f"读取电压或电流失败: {e}")

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
                print(f"PID控制执行成功，当前温度: {current_temp}°C")
            except Exception as e:
                print(f"PID控制执行失败: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PIDSystemUI()
    window.show()
    sys.exit(app.exec_())