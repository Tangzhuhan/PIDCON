import PyInstaller.__main__
import os
import platform

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 定义要包含的文件
data_files = [
    ('README.md', '.'),
]

# 构建数据文件参数
data_args = []
for src, dst in data_files:
    data_args.append('--add-data')
    data_args.append(f'{src}{os.pathsep}{dst}')

# 构建PyInstaller参数
pyinstaller_args = [
    'main.py',  # 主程序文件
    '--name=PID_Temperature_Control',  # 程序名称
    '--windowed',  # 不显示控制台窗口
    '--onefile',  # 打包成单个exe文件
    '--icon=icon.ico',  # 程序图标（如果有的话）
    '--clean',  # 清理临时文件
    '--noconfirm',  # 覆盖已存在的文件
]

# 添加数据文件参数
pyinstaller_args.extend(data_args)

# 添加其他必要的参数
if platform.system() == 'Windows':
    pyinstaller_args.extend([
        '--add-binary=serial;serial',  # Windows下需要包含serial模块
    ])

# 运行PyInstaller
PyInstaller.__main__.run(pyinstaller_args)