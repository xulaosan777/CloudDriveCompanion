import os
import sys
import re
import shutil
import subprocess
import random
import threading
import queue
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

# ================= 注册独立 App ID 与 高分屏 DPI 适配 =================
if sys.platform.startswith('win'):
    try:
        myappid = 'cloud_drive_companion.suite.v3'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ================= 数据持久化配置与老版本平滑迁移 =================
app_data_dir = os.getenv('APPDATA')
my_app_dir = os.path.join(app_data_dir, "CloudDriveCompanion")
old_app_dir = os.path.join(app_data_dir, "SmartExtractor")

if not os.path.exists(my_app_dir):
    os.makedirs(my_app_dir)

EXT_PWD_FILE = os.path.join(my_app_dir, "passwords.txt")
CMP_PWD_FILE = os.path.join(my_app_dir, "cmp_passwords.txt")

# 自动无感迁移老版本保存的密码记录
if os.path.exists(old_app_dir):
    old_ext = os.path.join(old_app_dir, "passwords.txt")
    old_cmp = os.path.join(old_app_dir, "cmp_passwords.txt")
    if os.path.exists(old_ext) and not os.path.exists(EXT_PWD_FILE):
        try: shutil.copy2(old_ext, EXT_PWD_FILE)
        except Exception: pass
    if os.path.exists(old_cmp) and not os.path.exists(CMP_PWD_FILE):
        try: shutil.copy2(old_cmp, CMP_PWD_FILE)
        except Exception: pass

TINY_JPEG_BYTES = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
    b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
    b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
    b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342'
    b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00'
    b'\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00'
    b'\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
)

def load_passwords(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except Exception:
            pass
    return []

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def open_password_manager(is_extract=True):
    target_file = EXT_PWD_FILE if is_extract else CMP_PWD_FILE
    target_combobox = ext_pwd_combobox if is_extract else cmp_pwd_combobox
    btn_color = ACCENT_BLUE if is_extract else ACCENT_PINK
    btn_hover = ACCENT_BLUE_HOV if is_extract else ACCENT_PINK_HOV
    win_title = "解压密码管理" if is_extract else "压缩密码管理"

    manager_win = tk.Toplevel(root)
    manager_win.title(win_title)
    manager_win.geometry("360x380")
    manager_win.configure(bg="#23242d")
    manager_win.transient(root)
    manager_win.grab_set()

    tk.Label(manager_win, text="已保存常用密码", bg="#23242d", fg="#8d99ae", font=("Microsoft YaHei UI", 9)).pack(pady=(15, 6))
    
    listbox = tk.Listbox(
        manager_win, width=34, height=9, bg="#1a1b22", fg="#edf2f4",
        selectbackground=btn_color, selectforeground="#ffffff",
        relief="flat", highlightthickness=1, highlightbackground="#3d405b", font=("Microsoft YaHei UI", 9)
    )
    listbox.pack(padx=15)
    for p in load_passwords(target_file):
        listbox.insert(tk.END, p)

    def sync_to_file():
        current_pwds = listbox.get(0, tk.END)
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                for p in current_pwds:
                    f.write(p + '\n')
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

    input_frame = tk.Frame(manager_win, bg="#23242d")
    input_frame.pack(pady=12, fill="x", padx=20)
    
    new_pwd_entry = tk.Entry(
        input_frame, bg="#1a1b22", fg="#edf2f4", insertbackground="#fff",
        relief="flat", highlightthickness=1, highlightbackground="#3d405b", font=("Microsoft YaHei UI", 9)
    )
    new_pwd_entry.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 8), ipady=3)
    
    add_btn = tk.Button(
        input_frame, text="添加", command=add_pwd,
        bg=btn_color, fg="#ffffff", activebackground=btn_hover, activeforeground="#fff",
        relief="flat", cursor="hand2", padx=12, pady=2, font=("Microsoft YaHei UI", 9)
    )
    add_btn.pack(side=tk.RIGHT)

    del_btn = tk.Button(
        manager_win, text="删除选中记录", command=del_pwd,
        bg="#ef233c", fg="#ffffff", activebackground="#d90429", activeforeground="#fff",
        relief="flat", cursor="hand2", pady=4, padx=12, font=("Microsoft YaHei UI", 9)
    )
    del_btn.pack(pady=(0, 10))

# ================= 核心工具函数 =================
def get_7za_path():
    return get_resource_path('7za.exe')

def update_status(text, progress_val=None, indeterminate=False):
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
    status_var.set("就绪 (支持多次拖入/批量拖入)")
    progress_bar.stop()
    progress_bar.config(mode='determinate')
    progress_var.set(0)

def format_size(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

# ================= 模块一：批量脱壳解压 =================
def detect_archive_type(filepath):
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
            if header.startswith(b'PK\x03\x04'):
                return 'zip'
            if header.startswith(b'7z\xbc\xaf\'\x1c'):
                return '7z'
            if header.startswith(b'Rar!\x1a\x07'):
                return 'rar'

            f.seek(0)
            chunk = f.read(15 * 1024 * 1024)
            if b'7z\xbc\xaf\'\x1c' in chunk:
                return '7z'
            if b'Rar!\x1a\x07' in chunk:
                return 'rar'
            if b'PK\x03\x04' in chunk:
                return 'zip'
    except Exception:
        pass

    match = re.search(r'(?i)\.(zip|7z|rar)(\.[^.]+)?$', os.path.basename(filepath))
    return match.group(1).lower() if match else None

def get_all_files_path(directory):
    return [os.path.join(r, f) for r, d, fs in os.walk(directory) for f in fs]

ext_tasks_dict = {}
ext_task_queue = queue.Queue()
is_ext_running = False

def extract_single_task(item_id, task_data, out_base_dir, threshold_mb, global_pwd, force_global_pwd, stop_threshold, keep_orig):
    exe_path = get_7za_path()
    start_file = task_data["filepath"]
    custom_pwd = task_data.get("pwd", "")
    effective_pwd = global_pwd if (force_global_pwd and global_pwd) else (custom_pwd or global_pwd)

    file_dir = os.path.dirname(os.path.abspath(start_file))
    target_base = out_base_dir.strip() if (out_base_dir and out_base_dir.strip()) else file_dir
    base_stem = os.path.splitext(os.path.basename(start_file))[0]
    task_out_dir = os.path.join(target_base, f"解压_{base_stem}")
    os.makedirs(task_out_dir, exist_ok=True)

    current_target = start_file
    layer = 1
    temp_dirs = []
    is_success = True

    try:
        while True:
            file_size = os.path.getsize(current_target)
            real_type = detect_archive_type(current_target)
            
            if not real_type:
                if layer == 1:
                    set_ext_tree_row(item_id, status="⏭️ 跳过 (非压缩文件)")
                    return False
                else:
                    set_ext_tree_row(item_id, status=f"✔ 完成 (穿透 {layer-1} 层)")
                break
                
            set_ext_tree_row(item_id, status=f"🔄 正在扒第 {layer} 层 ({real_type})")
            current_layer_dir = os.path.join(task_out_dir, f"temp_layer_{layer}")
            os.makedirs(current_layer_dir, exist_ok=True)
            temp_dirs.append(current_layer_dir)
            
            cmd = [exe_path, 'x', current_target, f'-t{real_type}', '-y', f'-o{current_layer_dir}']
            if effective_pwd:
                cmd.append(f'-p{effective_pwd}')
            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo:
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            res = subprocess.run(cmd, startupinfo=startupinfo, capture_output=True)
            if res.returncode != 0:
                cmd_fallback = [exe_path, 'x', current_target, '-y', f'-o{current_layer_dir}']
                if effective_pwd:
                    cmd_fallback.append(f'-p{effective_pwd}')
                res = subprocess.run(cmd_fallback, startupinfo=startupinfo, capture_output=True)

            if res.returncode != 0:
                set_ext_tree_row(item_id, status="❌ 失败 (密码错误/文件损坏)")
                is_success = False
                break
                
            all_files = get_all_files_path(current_layer_dir)
            item_count = len(all_files)
            
            if item_count > stop_threshold:
                set_ext_tree_row(item_id, status=f"✔ 完成 (终止符: {item_count} 文件)")
                break
            elif item_count == 1:
                current_target = all_files[0]
                layer += 1
                if len(temp_dirs) > 1:
                    shutil.rmtree(temp_dirs[-2], ignore_errors=True)
            else:
                set_ext_tree_row(item_id, status=f"✔ 完成 (散落 {item_count} 个文件)")
                break

        if is_success and temp_dirs:
            final_dest = os.path.join(task_out_dir, "最终提取文件")
            counter = 1
            while os.path.exists(final_dest):
                final_dest = os.path.join(task_out_dir, f"最终提取文件_{counter}")
                counter += 1
            try:
                os.rename(temp_dirs[-1], final_dest)
            except Exception:
                pass
            for d in temp_dirs[:-1]:
                shutil.rmtree(d, ignore_errors=True)
            
            if not keep_orig:
                try:
                    os.remove(start_file)
                except Exception:
                    pass
            return True
        elif not is_success:
            for d in temp_dirs:
                shutil.rmtree(d, ignore_errors=True)
            return False

    except Exception as e:
        set_ext_tree_row(item_id, status=f"❌ 出错: {str(e)[:15]}")
        return False

def ext_batch_worker_loop(out_base_dir, threshold_mb, global_pwd, force_global_pwd, stop_threshold, keep_orig):
    global is_ext_running
    total_tasks = ext_task_queue.qsize()
    done_count = 0

    while not ext_task_queue.empty():
        item_id = ext_task_queue.get()
        if item_id in ext_tasks_dict:
            task_data = ext_tasks_dict[item_id]
            file_name = os.path.basename(task_data["filepath"])
            update_status(f"正在脱壳 ({done_count+1}/{total_tasks}): {file_name}", progress_val=(done_count / total_tasks) * 100)
            
            extract_single_task(item_id, task_data, out_base_dir, threshold_mb, global_pwd, force_global_pwd, stop_threshold, keep_orig)
            done_count += 1
            progress_val = (done_count / total_tasks) * 100
            root.after(0, lambda v=progress_val: progress_var.set(v))
        ext_task_queue.task_done()

    is_ext_running = False
    root.after(0, reset_status)
    root.after(0, lambda: enable_ui(True))
    root.after(0, lambda: messagebox.showinfo("批量脱壳完成", f"队列任务全部执行完毕！\n共处理完成 {done_count} 个任务。"))

# ================= 模块二：批量伪装压缩 =================
cmp_tasks_dict = {}
cmp_task_queue = queue.Queue()
is_cmp_running = False

def compress_single_task(item_id, task_data, out_base_dir, layers, base_name, arch_format, disguise_ext, ext_mode, name_all, ext_all, pwd, pwd_all):
    exe_path = get_7za_path()
    source_path = task_data["filepath"]
    file_dir = os.path.dirname(os.path.abspath(source_path))
    target_out_dir = out_base_dir.strip() if (out_base_dir and out_base_dir.strip()) else file_dir

    temp_work_dir = os.path.join(target_out_dir, f"cmp_temp_{random.randint(1000, 9999)}")
    os.makedirs(temp_work_dir, exist_ok=True)

    if disguise_ext and disguise_ext != "无" and not disguise_ext.startswith('.'):
        disguise_ext = '.' + disguise_ext

    current_source = source_path
    stem_name = os.path.splitext(os.path.basename(source_path))[0]

    try:
        for i in range(1, layers + 1):
            is_first = (i == 1)      
            is_last = (i == layers)  
            set_cmp_tree_row(item_id, status=f"🔄 正在压缩第 {i}/{layers} 层")

            if base_name:
                c_name = base_name if (name_all or is_last) else str(random.randint(0, 999)).zfill(3)
            else:
                c_name = stem_name if (name_all or is_last) else str(random.randint(0, 999)).zfill(3)

            need_disguise = disguise_ext and disguise_ext != "无" and (ext_all or is_last)
            raw_archive_name = f"temp_{c_name}_{i}{arch_format}"
            target_archive = os.path.join(temp_work_dir, raw_archive_name)
            counter = 1
            while os.path.exists(target_archive):
                target_archive = os.path.join(temp_work_dir, f"temp_{c_name}_{i}_{counter}{arch_format}")
                counter += 1

            cmd = [exe_path, 'a', target_archive, current_source]
            if pwd and (pwd_all or is_first or is_last):
                cmd.append(f'-p{pwd}')
                if arch_format == '.7z':
                    cmd.append('-mhe=on')

            startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
            if startupinfo:
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            res = subprocess.run(cmd, startupinfo=startupinfo, capture_output=True)

            if res.returncode != 0:
                set_cmp_tree_row(item_id, status=f"❌ 第 {i} 层压缩失败")
                return False

            if need_disguise:
                final_ext = f"{arch_format}{disguise_ext}" if ext_mode == "append" else disguise_ext
                disguised_file = os.path.join(temp_work_dir, f"{c_name}{final_ext}")

                if ext_mode == "replace" and disguise_ext.lower() in [".jpg", ".jpeg"]:
                    with open(target_archive, 'rb') as f_in:
                        arch_data = f_in.read()
                    with open(disguised_file, 'wb') as f_out:
                        f_out.write(TINY_JPEG_BYTES)
                        f_out.write(arch_data)
                    os.remove(target_archive)
                else:
                    shutil.move(target_archive, disguised_file)
                current_source = disguised_file
            else:
                current_source = target_archive

        final_dest = os.path.join(target_out_dir, os.path.basename(current_source))
        if os.path.exists(final_dest):
            os.remove(final_dest)
        shutil.move(current_source, final_dest)
        set_cmp_tree_row(item_id, status="✔ 压缩完成")
        return True

    except Exception as e:
        set_cmp_tree_row(item_id, status=f"❌ 出错: {str(e)[:15]}")
        return False
    finally:
        shutil.rmtree(temp_work_dir, ignore_errors=True)

def cmp_batch_worker_loop(out_base_dir, layers, base_name, arch_format, disguise_ext, ext_mode, name_all, ext_all, pwd, pwd_all):
    global is_cmp_running
    total_tasks = cmp_task_queue.qsize()
    done_count = 0

    while not cmp_task_queue.empty():
        item_id = cmp_task_queue.get()
        if item_id in cmp_tasks_dict:
            task_data = cmp_tasks_dict[item_id]
            file_name = os.path.basename(task_data["filepath"])
            update_status(f"正在压缩 ({done_count+1}/{total_tasks}): {file_name}", progress_val=(done_count / total_tasks) * 100)

            compress_single_task(item_id, task_data, out_base_dir, layers, base_name, arch_format, disguise_ext, ext_mode, name_all, ext_all, pwd, pwd_all)
            done_count += 1
            progress_val = (done_count / total_tasks) * 100
            root.after(0, lambda v=progress_val: progress_var.set(v))
        cmp_task_queue.task_done()

    is_cmp_running = False
    root.after(0, reset_status)
    root.after(0, lambda: enable_ui(True))
    root.after(0, lambda: messagebox.showinfo("批量压缩完成", f"队列任务全部执行完毕！\n共完成封装 {done_count} 个任务。"))

# ================= UI 调度与独立密码弹窗 =================
def format_pwd_display(pwd):
    return "🔒 " + ("*" * min(len(pwd), 6)) + " ▾" if pwd else "⚙️ [跟随全局] ▾"

def set_ext_tree_row(item_id, status=None, pwd=None):
    def update():
        if not ext_task_tree.exists(item_id): return
        vals = list(ext_task_tree.item(item_id, "values"))
        if status is not None: vals[2] = status
        if pwd is not None: vals[3] = format_pwd_display(pwd)
        ext_task_tree.item(item_id, values=vals)
    root.after(0, update)

def set_cmp_tree_row(item_id, status=None):
    def update():
        if not cmp_task_tree.exists(item_id): return
        vals = list(cmp_task_tree.item(item_id, "values"))
        if status is not None: vals[2] = status
        cmp_task_tree.item(item_id, values=vals)
    root.after(0, update)

def add_files_to_ext_list(filepath_list):
    for path in filepath_list:
        path = path.strip('{}').strip('"')
        if not path or not os.path.exists(path):
            continue
        if os.path.isdir(path):
            sub_files = [os.path.join(r, f) for r, d, fs in os.walk(path) for f in fs]
            add_files_to_ext_list(sub_files)
            continue
        if any(task["filepath"] == path for task in ext_tasks_dict.values()):
            continue

        f_size = os.path.getsize(path)
        item_id = ext_task_tree.insert(
            "", tk.END,
            values=(os.path.basename(path), format_size(f_size), "⏳ 排队中", format_pwd_display(""), path)
        )
        ext_tasks_dict[item_id] = {"filepath": path, "pwd": "", "size": f_size}
    lbl_ext_count.config(text=f"当前任务数: {len(ext_tasks_dict)} 个")

def add_files_to_cmp_list(filepath_list):
    for path in filepath_list:
        path = path.strip('{}').strip('"')
        if not path or not os.path.exists(path):
            continue
        if any(task["filepath"] == path for task in cmp_tasks_dict.values()):
            continue

        f_size = os.path.getsize(path) if os.path.isfile(path) else 0
        display_name = os.path.basename(path) or path
        item_id = cmp_task_tree.insert(
            "", tk.END,
            values=(display_name, format_size(f_size) if os.path.isfile(path) else "文件夹", "⏳ 排队中", path)
        )
        cmp_tasks_dict[item_id] = {"filepath": path, "size": f_size}
    lbl_cmp_count.config(text=f"当前任务数: {len(cmp_tasks_dict)} 个")

def open_row_pwd_dialog(item_id):
    if is_ext_running: return
    task_data = ext_tasks_dict.get(item_id)
    if not task_data: return

    file_name = os.path.basename(task_data["filepath"])
    current_pwd = task_data.get("pwd", "")

    pwd_win = tk.Toplevel(root)
    pwd_win.title("专属解压密码配置")
    pwd_win.geometry("440x280")
    pwd_win.configure(bg="#23242d")
    pwd_win.transient(root)
    pwd_win.grab_set()

    x = root.winfo_x() + (root.winfo_width() // 2) - 220
    y = root.winfo_y() + (root.winfo_height() // 2) - 140
    pwd_win.geometry(f"+{x}+{y}")

    tk.Label(
        pwd_win, text="为文件配置专属解压密码:", bg="#23242d", fg=TEXT_MUTED,
        font=("Microsoft YaHei UI", 9)
    ).pack(pady=(18, 4), padx=24, anchor="w")

    tk.Label(
        pwd_win, text=file_name, bg="#23242d", fg=TEXT_MAIN,
        font=("Microsoft YaHei UI", 9, "bold"), wraplength=390, justify="left"
    ).pack(pady=(0, 14), padx=24, anchor="w")

    input_f = tk.Frame(pwd_win, bg="#23242d")
    input_f.pack(fill="x", padx=24, pady=(0, 10))

    saved_pwds = load_passwords(EXT_PWD_FILE)
    pwd_box = ttk.Combobox(input_f, values=saved_pwds, font=("Microsoft YaHei UI", 10))
    pwd_box.pack(fill="x", ipady=4)
    pwd_box.set(current_pwd)

    tk.Label(
        pwd_win, text="* 可手动输入，或展开下拉选用已保存常用密码\n* 清除留空时自动跟随全局解压密码",
        bg="#23242d", fg="#8d99ae", font=("Microsoft YaHei UI", 8), justify="left"
    ).pack(padx=24, anchor="w")

    btn_bar = tk.Frame(pwd_win, bg="#23242d")
    btn_bar.pack(side=tk.BOTTOM, fill="x", padx=24, pady=18)

    def on_confirm():
        val = pwd_box.get().strip()
        task_data["pwd"] = val
        set_ext_tree_row(item_id, pwd=val)
        pwd_win.destroy()

    def on_clear():
        task_data["pwd"] = ""
        set_ext_tree_row(item_id, pwd="")
        pwd_win.destroy()

    tk.Button(
        btn_bar, text="保存设置", command=on_confirm,
        bg=ACCENT_BLUE, fg="#fff", activebackground=ACCENT_BLUE_HOV, activeforeground="#fff",
        relief="flat", cursor="hand2", font=FONT_NORMAL, padx=16, pady=5
    ).pack(side=tk.RIGHT, padx=(10, 0))

    tk.Button(
        btn_bar, text="清除 (跟随全局)", command=on_clear,
        bg=ACCENT_BLUE, fg="#ffffff", activebackground=ACCENT_BLUE_HOV, activeforeground="#fff",
        relief="flat", cursor="hand2", font=FONT_NORMAL, padx=12, pady=5
    ).pack(side=tk.RIGHT)

def on_ext_tree_click(event):
    region = ext_task_tree.identify("region", event.x, event.y)
    if region != "cell": return
    col = ext_task_tree.identify_column(event.x)
    item_id = ext_task_tree.identify_row(event.y)
    if item_id and col == "#4":
        open_row_pwd_dialog(item_id)

def on_ext_tree_double_click(event):
    region = ext_task_tree.identify("region", event.x, event.y)
    if region != "cell": return
    item_id = ext_task_tree.identify_row(event.y)
    if item_id:
        open_row_pwd_dialog(item_id)

def run_ext_batch_thread():
    global is_ext_running
    if not ext_tasks_dict:
        return messagebox.showerror("提示", "脱壳任务列表为空，请拖入文件！")
    if is_ext_running or is_cmp_running:
        return messagebox.showwarning("提示", "有任务正在执行中，请稍候...")

    while not ext_task_queue.empty(): ext_task_queue.get()
    for item_id in ext_task_tree.get_children():
        ext_task_queue.put(item_id)
        set_ext_tree_row(item_id, status="⏳ 排队中")

    is_ext_running = True
    enable_ui(False)
    threading.Thread(
        target=ext_batch_worker_loop,
        args=(
            ext_out_var.get(),
            float(ext_size.get() or 100),
            ext_pwd_combobox.get(),
            ext_force_global_pwd_var.get(),
            int(ext_stop.get() or 2),
            ext_keep_var.get()
        ),
        daemon=True
    ).start()

def run_cmp_batch_thread():
    global is_cmp_running
    if not cmp_tasks_dict:
        return messagebox.showerror("提示", "压缩任务列表为空，请拖入文件！")
    if is_ext_running or is_cmp_running:
        return messagebox.showwarning("提示", "有任务正在执行中，请稍候...")

    while not cmp_task_queue.empty(): cmp_task_queue.get()
    for item_id in cmp_task_tree.get_children():
        cmp_task_queue.put(item_id)
        set_cmp_tree_row(item_id, status="⏳ 排队中")

    is_cmp_running = True
    enable_ui(False)
    threading.Thread(
        target=cmp_batch_worker_loop,
        args=(
            cmp_out_var.get(),
            int(cmp_layers.get() or 3),
            cmp_name.get().strip(),
            cmp_fmt.get(),
            cmp_ext.get(),
            cmp_ext_mode_var.get(),
            cmp_name_all.get(),
            cmp_ext_all.get(),
            cmp_pwd_combobox.get(),
            cmp_pwd_all.get()
        ),
        daemon=True
    ).start()

def enable_ui(state):
    s = 'normal' if state else 'disabled'
    btn_ext_start.config(state=s)
    btn_ext_add.config(state=s)
    btn_ext_clear.config(state=s)
    btn_cmp_start.config(state=s)
    btn_cmp_add_file.config(state=s)
    btn_cmp_add_dir.config(state=s)
    btn_cmp_clear.config(state=s)

current_tab_index = 0
def on_drop(event):
    raw_data = event.data
    files = re.findall(r'\{.*?\}|\S+', raw_data)
    clean_files = [f.strip('{}') for f in files]

    if current_tab_index == 0:
        add_files_to_ext_list(clean_files)
    else:
        add_files_to_cmp_list(clean_files)

# ----------------- 窗口初始化与主题配置 -----------------
if HAS_DND:
    root = TkinterDnD.Tk()
else:
    root = tk.Tk()

# 顶栏白边里的黑字严格设置为指定名称
root.title("智能网盘助手－批量解压与压缩")
root.geometry("920x680")
root.minsize(820, 600)
root.resizable(True, True)
root.configure(bg="#181920")

icon_file = get_resource_path("icon.ico")
if not os.path.exists(icon_file):
    icon_file = os.path.abspath("icon.ico")

if os.path.exists(icon_file):
    try:
        root.iconbitmap(default=icon_file)
    except Exception:
        pass

# 统一设计色彩常量
BG_DARK = "#181920"
CARD_BG = "#21222c"
CARD_BORDER = "#313442"
TEXT_MAIN = "#f8f9fa"
TEXT_MUTED = "#9ba3b0"
INPUT_BG = "#13141a"
ACCENT_BLUE = "#3a86ff"
ACCENT_BLUE_HOV = "#2667d4"
ACCENT_PINK = "#e63946"
ACCENT_PINK_HOV = "#d90429"
FONT_NORMAL = ("Microsoft YaHei UI", 9)
FONT_BTN = ("Microsoft YaHei UI", 10)

style = ttk.Style(root)
style.theme_use('clam')

style.configure(
    "Treeview",
    background=INPUT_BG,
    fieldbackground=INPUT_BG,
    foreground=TEXT_MAIN,
    borderwidth=0,
    font=("Microsoft YaHei UI", 9),
    rowheight=28
)
style.configure(
    "Treeview.Heading",
    background="#262835",
    foreground=TEXT_MUTED,
    borderwidth=0,
    font=("Microsoft YaHei UI", 9, "bold"),
    relief="flat"
)
style.map("Treeview.Heading", background=[("active", "#313442")])
style.map("Treeview", background=[("selected", "#3a86ff")], foreground=[("selected", "#ffffff")])

style.configure(
    "TCombobox",
    fieldbackground=INPUT_BG,
    background=CARD_BORDER,
    foreground=TEXT_MAIN,
    arrowcolor=TEXT_MUTED,
    relief="flat",
    borderwidth=0
)
style.map(
    "TCombobox",
    fieldbackground=[("readonly", INPUT_BG)],
    selectbackground=[("readonly", INPUT_BG)],
    selectforeground=[("readonly", TEXT_MAIN)]
)

style.configure(
    "Modern.Horizontal.TProgressbar",
    background=ACCENT_BLUE,
    troughcolor="#13141a",
    borderwidth=0,
    thickness=6
)

# ----------------- 底部状态栏 -----------------
bottom_frame = tk.Frame(root, bg="#13141a", padx=20, pady=10)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

status_var = tk.StringVar(value="就绪 (支持多次拖入/批量拖入)")
tk.Label(
    bottom_frame, textvariable=status_var, bg="#13141a", fg=TEXT_MUTED,
    font=FONT_NORMAL
).pack(side=tk.LEFT)

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(
    bottom_frame, variable=progress_var, maximum=100, length=240,
    style="Modern.Horizontal.TProgressbar"
)
progress_bar.pack(side=tk.RIGHT)

# ----------------- 主显示视口与弹性容器 -----------------
main_container = tk.Frame(root, bg=BG_DARK, padx=20, pady=12)
main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# 顶部导航按钮组（纯蓝/纯红动态样式切换）
nav_bar = tk.Frame(main_container, bg=BG_DARK)
nav_bar.pack(fill="x", anchor="w", pady=(0, 10))

tab_btn_ext = tk.Button(
    nav_bar, text="  🔓  批量脱壳解压  ", relief="flat", cursor="hand2",
    font=("Microsoft YaHei UI", 9), padx=20, pady=7, borderwidth=0
)
tab_btn_ext.pack(side=tk.LEFT)

tab_btn_cmp = tk.Button(
    nav_bar, text="  📦  批量伪装压缩  ", relief="flat", cursor="hand2",
    font=("Microsoft YaHei UI", 9), padx=20, pady=7, borderwidth=0
)
tab_btn_cmp.pack(side=tk.LEFT, padx=(6, 0))

content_box = tk.Frame(main_container, bg=BG_DARK)
content_box.pack(fill=tk.BOTH, expand=True)

ext_page = tk.Frame(content_box, bg=BG_DARK)
cmp_page = tk.Frame(content_box, bg=BG_DARK)

def switch_tab(index):
    global current_tab_index
    current_tab_index = index
    if index == 0:
        cmp_page.pack_forget()
        ext_page.pack(fill=tk.BOTH, expand=True)
        # 解压激活：全蓝底色 + 白色字体；压缩未激活：暗底
        tab_btn_ext.config(bg=ACCENT_BLUE, fg="#ffffff", activebackground=ACCENT_BLUE_HOV, activeforeground="#ffffff")
        tab_btn_cmp.config(bg="#1c1d26", fg=TEXT_MUTED, activebackground="#252733", activeforeground=TEXT_MAIN)
    else:
        ext_page.pack_forget()
        cmp_page.pack(fill=tk.BOTH, expand=True)
        # 压缩激活：全红底色 + 白色字体；解压未激活：暗底
        tab_btn_cmp.config(bg=ACCENT_PINK, fg="#ffffff", activebackground=ACCENT_PINK_HOV, activeforeground="#ffffff")
        tab_btn_ext.config(bg="#1c1d26", fg=TEXT_MUTED, activebackground="#252733", activeforeground=TEXT_MAIN)

tab_btn_ext.config(command=lambda: switch_tab(0))
tab_btn_cmp.config(command=lambda: switch_tab(1))

# ================= 页面 1：批量脱壳解压 (全蓝系按钮) =================
ext_strat_card = tk.Frame(ext_page, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER, padx=16, pady=10)
ext_strat_card.pack(fill="x", pady=(0, 10))
ext_strat_card.columnconfigure(1, weight=1)

ext_out_var = tk.StringVar()
ext_keep_var = tk.BooleanVar(value=True)
ext_force_global_pwd_var = tk.BooleanVar(value=True)

tk.Label(ext_strat_card, text="输出目录", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).grid(row=0, column=0, sticky="w", pady=4)
entry_ext_out = tk.Entry(
    ext_strat_card, textvariable=ext_out_var, bg=INPUT_BG, fg=TEXT_MAIN,
    insertbackground=TEXT_MAIN, relief="flat", highlightthickness=1,
    highlightbackground=CARD_BORDER, highlightcolor=ACCENT_BLUE, font=FONT_NORMAL
)
entry_ext_out.grid(row=0, column=1, sticky="ew", padx=(10, 8), ipady=3)

tk.Button(
    ext_strat_card, text="浏览...", command=lambda: ext_out_var.set(filedialog.askdirectory() or ext_out_var.get()),
    bg=ACCENT_BLUE, fg="#ffffff", activebackground=ACCENT_BLUE_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=FONT_NORMAL, padx=10, pady=1
).grid(row=0, column=2)

tk.Label(
    ext_strat_card, text="* 留空时：各文件解压至自身所在同级父目录下；指定时：全部集中至该目录",
    bg=CARD_BG, fg="#7a8290", font=("Microsoft YaHei UI", 8)
).grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(0, 4))

pwd_strat_f = tk.Frame(ext_strat_card, bg=CARD_BG)
pwd_strat_f.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 2))

tk.Label(pwd_strat_f, text="全局解压密码", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).pack(side=tk.LEFT)
ext_pwds = load_passwords(EXT_PWD_FILE)
ext_pwd_combobox = ttk.Combobox(pwd_strat_f, width=16, values=ext_pwds)
ext_pwd_combobox.pack(side=tk.LEFT, padx=(10, 8))
if ext_pwds:
    ext_pwd_combobox.set(ext_pwds[-1])

tk.Button(
    pwd_strat_f, text="管理常用", command=lambda: open_password_manager(is_extract=True),
    bg=ACCENT_BLUE, fg="#ffffff", activebackground=ACCENT_BLUE_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=("Microsoft YaHei UI", 8), padx=8, pady=1
).pack(side=tk.LEFT, padx=(0, 15))

tk.Checkbutton(
    pwd_strat_f, text="强制覆盖应用至所有任务 (优先于专属密码)", variable=ext_force_global_pwd_var,
    bg=CARD_BG, fg=TEXT_MAIN, activebackground=CARD_BG, activeforeground=TEXT_MAIN,
    selectcolor=INPUT_BG, font=FONT_NORMAL, cursor="hand2"
).pack(side=tk.LEFT)

ext_opt_f = tk.Frame(ext_strat_card, bg=CARD_BG)
ext_opt_f.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))

tk.Label(ext_opt_f, text="伪装体积阈值 (MB):", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).pack(side=tk.LEFT)
ext_size = tk.Entry(ext_opt_f, bg=INPUT_BG, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightthickness=1, highlightbackground=CARD_BORDER, font=FONT_NORMAL, width=6)
ext_size.insert(0, "100")
ext_size.pack(side=tk.LEFT, padx=(6, 15), ipady=2)

tk.Label(ext_opt_f, text="终止符(文件数>):", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).pack(side=tk.LEFT)
ext_stop = tk.Entry(ext_opt_f, bg=INPUT_BG, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightthickness=1, highlightbackground=CARD_BORDER, font=FONT_NORMAL, width=5)
ext_stop.insert(0, "2")
ext_stop.pack(side=tk.LEFT, padx=(6, 15), ipady=2)

tk.Checkbutton(
    ext_opt_f, text="解压完毕保留源文件", variable=ext_keep_var,
    bg=CARD_BG, fg=TEXT_MAIN, activebackground=CARD_BG, activeforeground=TEXT_MAIN,
    selectcolor=INPUT_BG, font=FONT_NORMAL, cursor="hand2"
).pack(side=tk.LEFT)

ext_tree_container = tk.Frame(ext_page, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER)
ext_tree_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

ext_task_tree = ttk.Treeview(
    ext_tree_container,
    columns=("filename", "size", "status", "pwd", "fullpath"),
    show="headings",
    selectmode="browse"
)
ext_task_tree.heading("filename", text="任务文件名称 (可多批拖入)")
ext_task_tree.heading("size", text="大小")
ext_task_tree.heading("status", text="执行状态")
ext_task_tree.heading("pwd", text="专属密码 (点击 ⚙️ 设置)")
ext_task_tree.heading("fullpath", text="完整路径")

ext_task_tree.column("filename", width=240, anchor="w")
ext_task_tree.column("size", width=80, anchor="center")
ext_task_tree.column("status", width=200, anchor="w")
ext_task_tree.column("pwd", width=160, anchor="center")
ext_task_tree.column("fullpath", width=220, anchor="w")

ext_tree_scroll = ttk.Scrollbar(ext_tree_container, orient="vertical", command=ext_task_tree.yview)
ext_task_tree.configure(yscrollcommand=ext_tree_scroll.set)

ext_task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
ext_tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

ext_task_tree.bind("<ButtonRelease-1>", on_ext_tree_click)
ext_task_tree.bind("<Double-1>", on_ext_tree_double_click)

ext_ctrl_bar = tk.Frame(ext_page, bg=BG_DARK)
ext_ctrl_bar.pack(fill="x")

lbl_ext_count = tk.Label(ext_ctrl_bar, text="当前任务数: 0 个", bg=BG_DARK, fg=TEXT_MUTED, font=FONT_NORMAL)
lbl_ext_count.pack(side=tk.LEFT)

def clear_ext_list():
    if is_ext_running:
        return messagebox.showwarning("提示", "正在执行批量解压，无法清空！")
    ext_task_tree.delete(*ext_task_tree.get_children())
    ext_tasks_dict.clear()
    lbl_ext_count.config(text="当前任务数: 0 个")

btn_ext_clear = tk.Button(
    ext_ctrl_bar, text="清空列表", command=clear_ext_list,
    bg=ACCENT_BLUE, fg="#ffffff", activebackground=ACCENT_BLUE_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=FONT_NORMAL, padx=12, pady=4
)
btn_ext_clear.pack(side=tk.RIGHT, padx=(8, 0))

def select_and_add_ext_files():
    fs = filedialog.askopenfilenames(title="选择要解压的文件（可多选）")
    if fs: add_files_to_ext_list(fs)

btn_ext_add = tk.Button(
    ext_ctrl_bar, text="➕ 添加文件...", command=select_and_add_ext_files,
    bg=ACCENT_BLUE, fg="#ffffff", activebackground=ACCENT_BLUE_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=FONT_NORMAL, padx=12, pady=4
)
btn_ext_add.pack(side=tk.RIGHT, padx=(8, 0))

btn_ext_start = tk.Button(
    ext_ctrl_bar, text="🚀 开始批量脱壳", command=run_ext_batch_thread,
    bg=ACCENT_BLUE, fg="#ffffff", activebackground=ACCENT_BLUE_HOV, activeforeground="#ffffff",
    relief="flat", cursor="hand2", font=FONT_BTN, padx=22, pady=5
)
btn_ext_start.pack(side=tk.RIGHT)

# ================= 页面 2：批量伪装压缩 (全红系按钮，对称架构) =================
cmp_strat_card = tk.Frame(cmp_page, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER, padx=16, pady=10)
cmp_strat_card.pack(fill="x", pady=(0, 10))
cmp_strat_card.columnconfigure(1, weight=1)

cmp_out_var = tk.StringVar()
cmp_ext_mode_var = tk.StringVar(value="append")
cmp_name_all = tk.BooleanVar(value=True)
cmp_ext_all = tk.BooleanVar(value=False)
cmp_pwd_all = tk.BooleanVar(value=False)

tk.Label(cmp_strat_card, text="输出目录", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).grid(row=0, column=0, sticky="w", pady=4)
entry_cmp_out = tk.Entry(
    cmp_strat_card, textvariable=cmp_out_var, bg=INPUT_BG, fg=TEXT_MAIN,
    insertbackground=TEXT_MAIN, relief="flat", highlightthickness=1,
    highlightbackground=CARD_BORDER, highlightcolor=ACCENT_PINK, font=FONT_NORMAL
)
entry_cmp_out.grid(row=0, column=1, sticky="ew", padx=(10, 8), ipady=3)

tk.Button(
    cmp_strat_card, text="浏览...", command=lambda: cmp_out_var.set(filedialog.askdirectory() or cmp_out_var.get()),
    bg=ACCENT_PINK, fg="#ffffff", activebackground=ACCENT_PINK_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=FONT_NORMAL, padx=10, pady=1
).grid(row=0, column=2)

tk.Label(
    cmp_strat_card, text="* 留空时：各文件压缩输出至各自同级父目录下；指定时：全部集中至该目录",
    bg=CARD_BG, fg="#7a8290", font=("Microsoft YaHei UI", 8)
).grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(0, 4))

cmp_row2_f = tk.Frame(cmp_strat_card, bg=CARD_BG)
cmp_row2_f.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 2))

tk.Label(cmp_row2_f, text="套娃层数:", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).pack(side=tk.LEFT)
cmp_layers = tk.Entry(cmp_row2_f, bg=INPUT_BG, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightthickness=1, highlightbackground=CARD_BORDER, font=FONT_NORMAL, width=5)
cmp_layers.insert(0, "3")
cmp_layers.pack(side=tk.LEFT, padx=(6, 15), ipady=2)

tk.Label(cmp_row2_f, text="基础命名:", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).pack(side=tk.LEFT)
cmp_name = tk.Entry(cmp_row2_f, bg=INPUT_BG, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightthickness=1, highlightbackground=CARD_BORDER, font=FONT_NORMAL, width=12)
cmp_name.pack(side=tk.LEFT, padx=(6, 8), ipady=2)

tk.Checkbutton(
    cmp_row2_f, text="应用至所有层 (留空使用源文件名)", variable=cmp_name_all,
    bg=CARD_BG, fg=TEXT_MAIN, activebackground=CARD_BG, activeforeground=TEXT_MAIN,
    selectcolor=INPUT_BG, font=("Microsoft YaHei UI", 8), cursor="hand2"
).pack(side=tk.LEFT)

cmp_row3_f = tk.Frame(cmp_strat_card, bg=CARD_BG)
cmp_row3_f.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 2))

tk.Label(cmp_row3_f, text="格式与伪装:", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).pack(side=tk.LEFT)
cmp_fmt = ttk.Combobox(cmp_row3_f, width=4, values=[".7z", ".zip"], state="readonly")
cmp_fmt.set(".7z")
cmp_fmt.pack(side=tk.LEFT, padx=(6, 2))
tk.Label(cmp_row3_f, text="+", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).pack(side=tk.LEFT, padx=2)
cmp_ext = ttk.Combobox(cmp_row3_f, width=6, values=["无", ".jpg", ".png", ".pdf", ".mp4"])
cmp_ext.set(".jpg")
cmp_ext.pack(side=tk.LEFT, padx=(2, 10))

tk.Radiobutton(
    cmp_row3_f, text="追加", variable=cmp_ext_mode_var, value="append",
    bg=CARD_BG, fg=TEXT_MAIN, activebackground=CARD_BG, activeforeground=TEXT_MAIN,
    selectcolor=INPUT_BG, font=("Microsoft YaHei UI", 8), cursor="hand2"
).pack(side=tk.LEFT, padx=(0, 4))
tk.Radiobutton(
    cmp_row3_f, text="替换(图种)", variable=cmp_ext_mode_var, value="replace",
    bg=CARD_BG, fg=TEXT_MAIN, activebackground=CARD_BG, activeforeground=TEXT_MAIN,
    selectcolor=INPUT_BG, font=("Microsoft YaHei UI", 8), cursor="hand2"
).pack(side=tk.LEFT, padx=(0, 10))

tk.Checkbutton(
    cmp_row3_f, text="伪装应用至所有层 (默认仅外层)", variable=cmp_ext_all,
    bg=CARD_BG, fg=TEXT_MAIN, activebackground=CARD_BG, activeforeground=TEXT_MAIN,
    selectcolor=INPUT_BG, font=("Microsoft YaHei UI", 8), cursor="hand2"
).pack(side=tk.LEFT)

cmp_row4_f = tk.Frame(cmp_strat_card, bg=CARD_BG)
cmp_row4_f.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(4, 0))

tk.Label(cmp_row4_f, text="统一压缩密码:", bg=CARD_BG, fg=TEXT_MUTED, font=FONT_NORMAL).pack(side=tk.LEFT)
cmp_pwds = load_passwords(CMP_PWD_FILE)
cmp_pwd_combobox = ttk.Combobox(cmp_row4_f, width=16, values=cmp_pwds)
cmp_pwd_combobox.pack(side=tk.LEFT, padx=(6, 8))
if cmp_pwds:
    cmp_pwd_combobox.set(cmp_pwds[-1])

tk.Button(
    cmp_row4_f, text="管理常用", command=lambda: open_password_manager(is_extract=False),
    bg=ACCENT_PINK, fg="#ffffff", activebackground=ACCENT_PINK_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=("Microsoft YaHei UI", 8), padx=8, pady=1
).pack(side=tk.LEFT, padx=(0, 15))

tk.Checkbutton(
    cmp_row4_f, text="加密所有层 (默认仅首尾加密)", variable=cmp_pwd_all,
    bg=CARD_BG, fg=TEXT_MAIN, activebackground=CARD_BG, activeforeground=TEXT_MAIN,
    selectcolor=INPUT_BG, font=FONT_NORMAL, cursor="hand2"
).pack(side=tk.LEFT)

cmp_tree_container = tk.Frame(cmp_page, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_BORDER)
cmp_tree_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

cmp_task_tree = ttk.Treeview(
    cmp_tree_container,
    columns=("filename", "size", "status", "fullpath"),
    show="headings",
    selectmode="browse"
)
cmp_task_tree.heading("filename", text="压缩目标 (文件/文件夹，可多批拖入)")
cmp_task_tree.heading("size", text="大小")
cmp_task_tree.heading("status", text="执行状态")
cmp_task_tree.heading("fullpath", text="完整路径")

cmp_task_tree.column("filename", width=280, anchor="w")
cmp_task_tree.column("size", width=90, anchor="center")
cmp_task_tree.column("status", width=200, anchor="w")
cmp_task_tree.column("fullpath", width=280, anchor="w")

cmp_tree_scroll = ttk.Scrollbar(cmp_tree_container, orient="vertical", command=cmp_task_tree.yview)
cmp_task_tree.configure(yscrollcommand=cmp_tree_scroll.set)

cmp_task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
cmp_tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

cmp_ctrl_bar = tk.Frame(cmp_page, bg=BG_DARK)
cmp_ctrl_bar.pack(fill="x")

lbl_cmp_count = tk.Label(cmp_ctrl_bar, text="当前任务数: 0 个", bg=BG_DARK, fg=TEXT_MUTED, font=FONT_NORMAL)
lbl_cmp_count.pack(side=tk.LEFT)

def clear_cmp_list():
    if is_cmp_running:
        return messagebox.showwarning("提示", "正在执行批量压缩，无法清空！")
    cmp_task_tree.delete(*cmp_task_tree.get_children())
    cmp_tasks_dict.clear()
    lbl_cmp_count.config(text="当前任务数: 0 个")

btn_cmp_clear = tk.Button(
    cmp_ctrl_bar, text="清空列表", command=clear_cmp_list,
    bg=ACCENT_PINK, fg="#ffffff", activebackground=ACCENT_PINK_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=FONT_NORMAL, padx=12, pady=4
)
btn_cmp_clear.pack(side=tk.RIGHT, padx=(8, 0))

def select_and_add_cmp_files():
    fs = filedialog.askopenfilenames(title="选择要压缩的文件（可多选）")
    if fs: add_files_to_cmp_list(fs)

def select_and_add_cmp_dir():
    d = filedialog.askdirectory(title="选择要压缩的文件夹")
    if d: add_files_to_cmp_list([d])

btn_cmp_add_dir = tk.Button(
    cmp_ctrl_bar, text="📁 添加文件夹...", command=select_and_add_cmp_dir,
    bg=ACCENT_PINK, fg="#ffffff", activebackground=ACCENT_PINK_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=FONT_NORMAL, padx=10, pady=4
)
btn_cmp_add_dir.pack(side=tk.RIGHT, padx=(6, 0))

btn_cmp_add_file = tk.Button(
    cmp_ctrl_bar, text="➕ 添加文件...", command=select_and_add_cmp_files,
    bg=ACCENT_PINK, fg="#ffffff", activebackground=ACCENT_PINK_HOV, activeforeground="#fff",
    relief="flat", cursor="hand2", font=FONT_NORMAL, padx=10, pady=4
)
btn_cmp_add_file.pack(side=tk.RIGHT, padx=(8, 0))

btn_cmp_start = tk.Button(
    cmp_ctrl_bar, text="📦 开始批量封装", command=run_cmp_batch_thread,
    bg=ACCENT_PINK, fg="#ffffff", activebackground=ACCENT_PINK_HOV, activeforeground="#ffffff",
    relief="flat", cursor="hand2", font=FONT_BTN, padx=22, pady=5
)
btn_cmp_start.pack(side=tk.RIGHT)

# 默认激活批量脱壳（蓝色态）
switch_tab(0)

if HAS_DND:
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', on_drop)

root.mainloop()