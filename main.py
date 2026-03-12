import os
import sys
import re
import shutil
import subprocess
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

# 尝试导入拖拽库
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ================= 数据持久化配置 =================
app_data_dir = os.getenv('APPDATA')
my_app_dir = os.path.join(app_data_dir, "SmartExtractor")
if not os.path.exists(my_app_dir):
    os.makedirs(my_app_dir)

EXT_PWD_FILE = os.path.join(my_app_dir, "passwords.txt")
CMP_PWD_FILE = os.path.join(my_app_dir, "cmp_passwords.txt")

def load_passwords(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except Exception: pass
    return []

def open_password_manager(is_extract=True):
    target_file = EXT_PWD_FILE if is_extract else CMP_PWD_FILE
    target_combobox = ext_pwd_combobox if is_extract else cmp_pwd_combobox
    win_title = "解压密码管理" if is_extract else "压缩密码管理"

    manager_win = tk.Toplevel(root)
    manager_win.title(win_title)
    manager_win.geometry("300x280")
    manager_win.transient(root)
    manager_win.grab_set()

    tk.Label(manager_win, text="已保存的常用密码:").pack(pady=(10, 5))
    listbox = tk.Listbox(manager_win, width=30, height=8)
    listbox.pack()
    for p in load_passwords(target_file): listbox.insert(tk.END, p)
        
    def sync_to_file():
        current_pwds = listbox.get(0, tk.END)
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                for p in current_pwds: f.write(p + '\n')
            target_combobox['values'] = current_pwds
            if not target_combobox.get() and current_pwds:
                target_combobox.set(current_pwds[-1])
        except Exception as e:
            messagebox.showerror("错误", f"保存密码失败: {e}")

    def add_pwd():
        new_p = new_pwd_entry.get().strip()
        if new_p and new_p not in listbox.get(0, tk.END):
            listbox.insert(tk.END, new_p)
            new_pwd_entry.delete(0, tk.END)
            sync_to_file()

    def del_pwd():
        selected = listbox.curselection()
        if selected:
            listbox.delete(selected[0])
            sync_to_file()

    input_frame = tk.Frame(manager_win)
    input_frame.pack(pady=10)
    new_pwd_entry = tk.Entry(input_frame, width=20)
    new_pwd_entry.pack(side=tk.LEFT, padx=5)
    tk.Button(input_frame, text="添加", command=add_pwd).pack(side=tk.LEFT)
    tk.Button(manager_win, text="删除选中项", command=del_pwd, fg="red").pack()

# ================= 核心工具函数 =================
def get_7za_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, '7za.exe')
    return os.path.join(os.path.abspath("."), '7za.exe')

def update_status(text, progress_val=None, indeterminate=False):
    """更新底部状态栏和进度条"""
    status_var.set(text)
    if indeterminate:
        progress_bar.config(mode='indeterminate')
        progress_bar.start(10)
    else:
        progress_bar.stop()
        progress_bar.config(mode='determinate')
        if progress_val is not None:
            progress_var.set(progress_val)

def reset_status():
    status_var.set("就绪")
    progress_bar.stop()
    progress_bar.config(mode='determinate')
    progress_var.set(0)

# ================= 模块一：脱壳解压 =================
def detect_archive_type(filepath):
    try:
        with open(filepath, 'rb') as f: header = f.read(8)
        if header.startswith(b'PK\x03\x04'): return 'zip'
        if header.startswith(b'7z\xbc\xaf\'\x1c'): return '7z'
        if header.startswith(b'Rar!\x1a\x07'): return 'rar' 
    except Exception: pass
    match = re.search(r'(?i)\.(zip|7z|rar)(\.[^.]+)?$', os.path.basename(filepath))
    return match.group(1).lower() if match else None

def get_all_files_path(directory):
    return [os.path.join(r, f) for r, d, fs in os.walk(directory) for f in fs]

def smart_extract_process(start_file, out_dir, threshold_mb, global_pwd, stop_threshold, keep_orig):
    try:
        exe_path = get_7za_path()
        current_target = start_file
        layer = 1
        temp_dirs = []
        is_success = True # 新增状态拦截器
        update_status("正在启动脱壳引擎...", indeterminate=True)

        while True:
            file_size = os.path.getsize(current_target)
            real_type = detect_archive_type(current_target)
            
            if not real_type:
                if file_size >= threshold_mb * 1024 * 1024:
                    update_status(f"文件大于阈值但无格式特征，停止于第 {layer} 层", indeterminate=False)
                else:
                    update_status(f"成功触达底层真实文件，共扒开 {layer-1} 层", indeterminate=False)
                break
                
            update_status(f"正在破解并解压第 {layer} 层 (格式: {real_type})...", indeterminate=True)
            current_layer_dir = os.path.join(out_dir, f"temp_extract_layer_{layer}")
            os.makedirs(current_layer_dir, exist_ok=True)
            temp_dirs.append(current_layer_dir)
            
            cmd = [exe_path, 'x', current_target, '-y', f'-o{current_layer_dir}']
            if global_pwd: cmd.append(f'-p{global_pwd}')
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            res = subprocess.run(cmd, startupinfo=startupinfo, capture_output=True)
            
            # 密码错误或损坏判断
            if res.returncode != 0:
                update_status(f"解压中断：第 {layer} 层解压失败", indeterminate=False)
                is_success = False
                break
                
            all_files = get_all_files_path(current_layer_dir)
            item_count = len(all_files)
            
            if item_count > stop_threshold:
                update_status(f"触发终止符：找到 {item_count} 个文件，解压彻底完成", indeterminate=False)
                break
            elif item_count == 1:
                current_target = all_files[0]
                layer += 1
                if len(temp_dirs) > 1: shutil.rmtree(temp_dirs[-2], ignore_errors=True)
            else:
                update_status(f"停止：散落 {item_count} 个文件，等待人工检查", indeterminate=False)
                break

        # 根据拦截器判断最终输出
        if is_success and temp_dirs:
            final_dest = os.path.join(out_dir, "最终解压结果")
            counter = 1
            while os.path.exists(final_dest):
                final_dest = os.path.join(out_dir, f"最终解压结果_{counter}")
                counter += 1
            try: os.rename(temp_dirs[-1], final_dest)
            except Exception: pass
            for d in temp_dirs[:-1]: shutil.rmtree(d, ignore_errors=True)
            
            if not keep_orig:
                try: os.remove(start_file)
                except Exception: pass
                
            root.after(0, lambda: messagebox.showinfo("完成", "解压任务结束，请查看结果。"))
        elif not is_success:
            # 失败时清理所有产生的垃圾文件
            for d in temp_dirs: shutil.rmtree(d, ignore_errors=True)
            root.after(0, lambda: messagebox.showerror("解压失败", "密码错误或文件已损坏，任务已终止。"))

    except Exception as e:
        root.after(0, lambda: messagebox.showerror("严重错误", str(e)))
    finally:
        root.after(0, reset_status)
        root.after(0, lambda: enable_ui(True))

# ================= 模块二：套娃压缩 =================
def smart_compress_process(source_path, out_dir, layers, base_name, arch_format, disguise_ext, ext_mode, name_all, ext_all, pwd, pwd_all):
    try:
        exe_path = get_7za_path()
        current_source = source_path
        temp_work_dir = os.path.join(out_dir, "compress_temp_workplace")
        os.makedirs(temp_work_dir, exist_ok=True)
        
        if disguise_ext and disguise_ext != "无" and not disguise_ext.startswith('.'):
            disguise_ext = '.' + disguise_ext

        for i in range(1, layers + 1):
            is_first = (i == 1)      
            is_last = (i == layers)  
            
            update_status(f"正在进行套娃压缩：第 {i} 层 / 共 {layers} 层...", progress_val=(i/layers)*100)
            
            if base_name and (name_all or is_last): c_name = base_name
            else: c_name = str(random.randint(0, 999)).zfill(3)
                
            if disguise_ext and disguise_ext != "无" and (ext_all or is_last):
                if ext_mode == "append": f_ext = f"{arch_format}{disguise_ext}"
                else: f_ext = disguise_ext 
            else: 
                f_ext = arch_format
                
            target_archive = os.path.join(temp_work_dir, f"{c_name}{f_ext}")
            counter = 1
            while os.path.exists(target_archive):
                target_archive = os.path.join(temp_work_dir, f"{c_name}_{counter}{f_ext}")
                counter += 1
            
            cmd = [exe_path, 'a', target_archive, current_source]
            
            if pwd and (pwd_all or is_first or is_last):
                cmd.append(f'-p{pwd}')
                if arch_format == '.7z': cmd.append('-mhe=on')
            
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo: startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            res = subprocess.run(cmd, startupinfo=startupinfo, capture_output=True)
            
            if res.returncode != 0:
                update_status(f"第 {i} 层压缩失败！")
                root.after(0, lambda: messagebox.showerror("错误", f"第 {i} 层压缩失败。"))
                return
            current_source = target_archive

        final_path = os.path.join(out_dir, os.path.basename(current_source))
        if os.path.exists(final_path): os.remove(final_path)
        shutil.move(current_source, final_path)
        
        root.after(0, lambda: messagebox.showinfo("完成", f"套娃封装结束！\n最终文件: {os.path.basename(final_path)}"))
    except Exception as e:
        root.after(0, lambda: messagebox.showerror("严重错误", str(e)))
    finally:
        shutil.rmtree(temp_work_dir, ignore_errors=True)
        root.after(0, reset_status)
        root.after(0, lambda: enable_ui(True))

# ================= UI 界面与多线程调度 =================
def run_ext_thread():
    if not ext_file_var.get(): return messagebox.showerror("错误", "未选择解压目标文件")
    enable_ui(False)
    threading.Thread(target=smart_extract_process, args=(ext_file_var.get(), ext_out_var.get(), float(ext_size.get()), ext_pwd_combobox.get(), int(ext_stop.get()), ext_keep_var.get()), daemon=True).start()

def run_cmp_thread():
    if not cmp_file_var.get(): return messagebox.showerror("错误", "未选择压缩目标")
    enable_ui(False)
    threading.Thread(target=smart_compress_process, args=(cmp_file_var.get(), cmp_out_var.get(), int(cmp_layers.get()), cmp_name.get(), cmp_fmt.get(), cmp_ext.get(), cmp_ext_mode_var.get(), cmp_name_all.get(), cmp_ext_all.get(), cmp_pwd_combobox.get(), cmp_pwd_all.get()), daemon=True).start()

def enable_ui(state):
    s = 'normal' if state else 'disabled'
    btn_ext_start.config(state=s)
    btn_cmp_start.config(state=s)

def on_drop(event):
    filepath = event.data.strip('{}')
    if notebook.index(notebook.select()) == 0:
        ext_file_var.set(filepath)
        ext_out_var.set(os.path.dirname(filepath))
    else:
        cmp_file_var.set(filepath)
        cmp_out_var.set(os.path.dirname(filepath))

if HAS_DND: root = TkinterDnD.Tk()
else: root = tk.Tk()

root.title("智能脱壳与封装工具 (Smart Extractor & Packer)")
root.geometry("560x520")
root.resizable(False, False)

if HAS_DND:
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', on_drop)

notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True, padx=5, pady=5)

# --------- 选项卡1：脱壳解压 ---------
ext_tab = ttk.Frame(notebook)
notebook.add(ext_tab, text="🔓 脱壳解压")

ext_file_var = tk.StringVar()
ext_out_var = tk.StringVar()
ext_keep_var = tk.BooleanVar(value=True) 

tk.Label(ext_tab, text="目标文件(可拖入):").grid(row=0, column=0, padx=10, pady=15, sticky="e")
tk.Entry(ext_tab, textvariable=ext_file_var, width=38).grid(row=0, column=1)
tk.Button(ext_tab, text="浏览", command=lambda: ext_file_var.set(filedialog.askopenfilename() or ext_file_var.get())).grid(row=0, column=2, padx=5)

tk.Label(ext_tab, text="输出目录:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
tk.Entry(ext_tab, textvariable=ext_out_var, width=38).grid(row=1, column=1)
tk.Button(ext_tab, text="浏览", command=lambda: ext_out_var.set(filedialog.askdirectory() or ext_out_var.get())).grid(row=1, column=2, padx=5)

tk.Label(ext_tab, text="伪装体积阈值 (MB):").grid(row=2, column=0, padx=10, pady=10, sticky="e")
ext_size = tk.Entry(ext_tab, width=15)
ext_size.insert(0, "100") 
ext_size.grid(row=2, column=1, sticky="w")

tk.Label(ext_tab, text="全局解压密码:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
ext_pwds = load_passwords(EXT_PWD_FILE)
ext_pwd_combobox = ttk.Combobox(ext_tab, width=15, values=ext_pwds)
ext_pwd_combobox.grid(row=3, column=1, sticky="w")
if ext_pwds: ext_pwd_combobox.set(ext_pwds[-1])
tk.Button(ext_tab, text="管理常用", command=lambda: open_password_manager(is_extract=True)).grid(row=3, column=1, sticky="e", padx=25)

tk.Label(ext_tab, text="终止符(文件数>):").grid(row=4, column=0, padx=10, pady=10, sticky="e")
ext_stop = tk.Entry(ext_tab, width=15)
ext_stop.insert(0, "2")
ext_stop.grid(row=4, column=1, sticky="w")

tk.Checkbutton(ext_tab, text="处理完毕后保留源文件", variable=ext_keep_var).grid(row=5, column=1, pady=5, sticky="w")

btn_ext_start = tk.Button(ext_tab, text="开始脱壳解压", command=run_ext_thread, width=25, bg="#add8e6")
btn_ext_start.grid(row=6, column=0, columnspan=3, pady=15)

# --------- 选项卡2：套娃压缩 ---------
cmp_tab = ttk.Frame(notebook)
notebook.add(cmp_tab, text="📦 伪装压缩")

cmp_file_var = tk.StringVar()
cmp_out_var = tk.StringVar()
cmp_ext_mode_var = tk.StringVar(value="append") 
cmp_name_all = tk.BooleanVar(value=True)
cmp_ext_all = tk.BooleanVar(value=True)
cmp_pwd_all = tk.BooleanVar(value=False)

tk.Label(cmp_tab, text="目标内容(可拖入):").grid(row=0, column=0, padx=10, pady=15, sticky="e")
tk.Entry(cmp_tab, textvariable=cmp_file_var, width=38).grid(row=0, column=1)
def cmp_browse():
    path = filedialog.askdirectory(title="选择要压缩的文件夹")
    if not path: path = filedialog.askopenfilename(title="或选择要压缩的文件")
    if path: cmp_file_var.set(path)
tk.Button(cmp_tab, text="浏览", command=cmp_browse).grid(row=0, column=2, padx=5)

tk.Label(cmp_tab, text="输出目录:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
tk.Entry(cmp_tab, textvariable=cmp_out_var, width=38).grid(row=1, column=1)
tk.Button(cmp_tab, text="浏览", command=lambda: cmp_out_var.set(filedialog.askdirectory() or cmp_out_var.get())).grid(row=1, column=2, padx=5)

tk.Label(cmp_tab, text="套娃压缩层数:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
cmp_layers = tk.Entry(cmp_tab, width=10)
cmp_layers.insert(0, "3")
cmp_layers.grid(row=2, column=1, sticky="w")

tk.Label(cmp_tab, text="自定义名称:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
cmp_name = tk.Entry(cmp_tab, width=15)
cmp_name.grid(row=3, column=1, sticky="w")
tk.Checkbutton(cmp_tab, text="应用到所有层(否则内层随机)", variable=cmp_name_all).grid(row=3, column=1, sticky="e")

tk.Label(cmp_tab, text="格式与伪装后缀:").grid(row=4, column=0, padx=10, pady=10, sticky="e")
f_frame = tk.Frame(cmp_tab)
f_frame.grid(row=4, column=1, sticky="w")
cmp_fmt = ttk.Combobox(f_frame, width=4, values=[".7z", ".zip"], state="readonly")
cmp_fmt.set(".7z")
cmp_fmt.pack(side=tk.LEFT)
tk.Label(f_frame, text="+").pack(side=tk.LEFT)
cmp_ext = ttk.Combobox(f_frame, width=5, values=["无", ".jpg", ".png", ".pdf", ".mp4"])
cmp_ext.set(".jpg")
cmp_ext.pack(side=tk.LEFT)

mode_frame = tk.Frame(cmp_tab)
mode_frame.grid(row=4, column=1, sticky="e")
tk.Radiobutton(mode_frame, text="追加", variable=cmp_ext_mode_var, value="append").pack(side=tk.LEFT)
tk.Radiobutton(mode_frame, text="替换", variable=cmp_ext_mode_var, value="replace").pack(side=tk.LEFT)

tk.Checkbutton(cmp_tab, text="应用到所有层(否则仅外层伪装)", variable=cmp_ext_all).grid(row=5, column=1, sticky="w")

tk.Label(cmp_tab, text="统一压缩密码:").grid(row=6, column=0, padx=10, pady=10, sticky="e")
cmp_pwds = load_passwords(CMP_PWD_FILE)
cmp_pwd_combobox = ttk.Combobox(cmp_tab, width=15, values=cmp_pwds)
cmp_pwd_combobox.grid(row=6, column=1, sticky="w")
if cmp_pwds: cmp_pwd_combobox.set(cmp_pwds[-1])
tk.Button(cmp_tab, text="管理常用", command=lambda: open_password_manager(is_extract=False)).grid(row=6, column=1, sticky="e", padx=25)
tk.Checkbutton(cmp_tab, text="应用到所有层(否则仅首尾加密)", variable=cmp_pwd_all).grid(row=7, column=1, sticky="w")

btn_cmp_start = tk.Button(cmp_tab, text="开始伪装压缩", command=run_cmp_thread, width=25, bg="#ffb6c1")
btn_cmp_start.grid(row=8, column=0, columnspan=3, pady=5)

# --------- 底部状态栏与进度条 ---------
bottom_frame = tk.Frame(root)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

status_var = tk.StringVar(value="就绪")
tk.Label(bottom_frame, textvariable=status_var, fg="gray").pack(side=tk.LEFT)

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(bottom_frame, variable=progress_var, maximum=100, length=200)
progress_bar.pack(side=tk.RIGHT)

root.mainloop()