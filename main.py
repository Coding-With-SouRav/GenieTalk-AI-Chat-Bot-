import ctypes
import math
import os
import re
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import google.generativeai as genai
import configparser
from sys import platform
from PIL import Image, ImageTk
import json
from datetime import datetime


if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YourAppID.UniqueName")

if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
else:
    exe_dir = os.path.abspath(".")

class CircularLoader(tk.Canvas):
    def __init__(self, parent, radius=40, dot_radius=5, num_dots=12, speed=100, **kwargs):
        super().__init__(parent, width=radius*2+20, height=radius*2+20, bg=parent.cget('bg'), highlightthickness=0, **kwargs)
        self.radius = radius
        self.dot_radius = dot_radius
        self.num_dots = num_dots
        self.speed = speed
        self.angle = 0
        self.dots = []

        self.create_dots()
        self.animate()

    def create_dots(self):
        self.dots.clear()
        for i in range(self.num_dots):
            angle = 2 * math.pi * i / self.num_dots
            x = self.radius * math.cos(angle) + self.radius + 10
            y = self.radius * math.sin(angle) + self.radius + 10
            dot = self.create_oval(
                x - self.dot_radius, y - self.dot_radius,
                x + self.dot_radius, y + self.dot_radius,
                fill="white", outline=""
            )
            self.dots.append(dot)

    def animate(self):
        self.angle = (self.angle + 1) % self.num_dots
        for i, dot in enumerate(self.dots):
            index = (i - self.angle) % self.num_dots
            brightness = 255 - int((index / self.num_dots) * 200)
            color = f"#{brightness:02x}{brightness:02x}{brightness:02x}"
            self.itemconfig(dot, fill=color)
        self.after(self.speed, self.animate)

chat_history = []
placeholder = "\n     Typing..."
config_file = os.path.join(exe_dir, 'config.ini')
current_animation_id = None
is_processing = False
stop_requested = False
app_running = True
auto_scroll_enabled = True
last_scroll_position = (0, 0)
normal_geometry = ""
is_animating = False 
sidebar_width = 250
sidebar_shown = False
current_width = 0
history_shown = False
history_sidebar_height = 0
buttons_y_positions = []
current_loader = None 
current_chat_title = ""
history_frame = None
canvas1_visible = False
canvas2_visible = False
canvas3_visible = False

dark_gray = "#404040"



GENAI_API_KEY = "AIzaSyCgepCd72RunvdGLuD-258qaawcWeHBubg" 
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
chat = model.start_chat(history=[]) 


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    full_path = os.path.join(base_path, relative_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Resource not found: {full_path}")
    return full_path


def load_window_geometry():
    global normal_geometry
    if os.path.exists(config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        if "Geometry" in config:
            normal_geometry = config["Geometry"].get("normal_geometry", "")
            state = config["Geometry"].get("state", "normal")
            
            if normal_geometry:
                root.geometry(normal_geometry)
            if state == "zoomed":
                root.state("zoomed")
            elif state == "iconic":
                root.iconify()

def save_window_geometry():
    config = configparser.ConfigParser()
    config["Geometry"] = {
        "normal_geometry": normal_geometry,
        "state": root.state()
    }
    with open(config_file, "w") as f:
        config.write(f)

def track_geometry(event):
    global normal_geometry
    if root.state() == 'normal':
        normal_geometry = root.geometry()
    if sidebar_shown:
        sidebar.place_configure(height=root.winfo_height())


def on_close():
    global app_running
    app_running = False
    if root.state() == 'zoomed':
        root.state('normal')
        root.update()
        track_geometry(None)
        root.state('zoomed')
    save_current_chat()
    save_window_geometry()
    root.destroy()


def on_canvas_configure(event):
    canvas.itemconfig(window_id, width=event.width)
    canvas.configure(scrollregion=canvas.bbox('all'))
    update_nexabot() 

def on_message_frame_configure(event):
    new_wraplength = int(0.8 * event.width)
    for label in message_frame.winfo_children():
        if isinstance(label, tk.Label):
            label.config(wraplength=new_wraplength)

def on_focusin(event):
    current_text = user_input.get("1.0", "end-1c").strip()
    if current_text == placeholder.strip():
        user_input.delete("1.0", "end")
        user_input.tag_remove("placeholder", "1.0", "end")
    toggle_send_button()  

def on_focusout(event):
    current_text = user_input.get("1.0", "end-1c").strip()
    if not current_text.strip():
        user_input.insert("1.0", placeholder, "placeholder")
        user_input.tag_add("placeholder", "1.0", "end")
    toggle_send_button()  


def adjust_input_height(event=None):
    max_lines = 11
    content = user_input.get("1.0", "end-1c")
    lines = content.split("\n")
    line_count = len(lines)

    if not content.strip():
        user_input.configure(height=4)
        text_scrollbar.pack_forget()
        return
    
    line_count = int(user_input.count("1.0", "end", "displaylines")[0])
    
    new_height = min(max(1, line_count), max_lines)
    user_input.configure(height=new_height)

    if line_count < 4:
        user_input.configure(height=4)

    current_height = user_input.cget("height")
    if line_count > current_height:  
        text_scrollbar.pack(side=tk.LEFT, fill=tk.Y)
    else:
        text_scrollbar.pack_forget()
    user_input.see("end")


def insert_message(msg, sender='user'):
    global auto_scroll_enabled, current_loader
    auto_scroll_enabled = True  
    if not app_running:  
        return
    current_wraplength = int(0.8 * message_frame.winfo_width())
    if sender == 'user':
        if current_loader is not None:
            current_loader.destroy()
            current_loader = None

        container = tk.Frame(message_frame, bg='#7876a9')
        container.pack(anchor='e', pady=30, padx=10)

        current_loader = CircularLoader(
            container,
            radius=10,
            dot_radius=1.2,
            speed=50,
        )
        current_loader.pack(side=tk.LEFT,anchor="sw", padx=(0, 10))

        label = tk.Text(container,
                            wrap='none',
                            bg='#7876a9',
                            fg='white', 
                            font=('Arial', 15),
                            border=0,
                            borderwidth=0,
                            padx=30, 
                            pady=20,
                            state='normal',  
                            insertwidth=0 
                            )
        label.pack(side=tk.RIGHT)

        def adjust_size_and_insert(text):
            processed_lines = process_message(text)
            processed_content = '\n'.join(processed_lines)
            label.config(state='normal')
            label.delete('1.0', 'end')
            label.insert('1.0', processed_content)
            label.config(state='disabled')
            max_length = max(len(line) for line in processed_lines) if processed_lines else 0
            label.config(
                width=min(max_length, 60),
                height=len(processed_lines)
            )

        adjust_size_and_insert(msg)
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox('all'))
        label.bind("<Button-1>", lambda e: root.focus_set())
        label.bind("<Key>", handle_key_event)
        label.bind("<Control-c>", copy_text)
        label.bind("<Control-C>", copy_text)
        label.bind("<Button-1>", lambda e: label.focus_set())
        canvas.yview_moveto(1)
    elif sender == 'bot':
        if current_loader is not None:
            current_loader.destroy()
            current_loader = None

        label = tk.Text(message_frame,
                        wrap='none',
                        bg='#1a1a1a',
                        fg='white',
                        font=('Arial', 15),
                        border=0,
                        borderwidth=0,
                        state='normal',  
                        padx=30,
                        pady=20,
                        insertwidth=0   
                        )
        label.pack(anchor='w', pady=20, padx=10)
        label.bind("<Key>", handle_key_event)
        label.bind("<Control-c>", copy_text)
        label.bind("<Control-C>", copy_text)
        label.bind("<Button-1>", lambda e: label.focus_set())
        animate_typing(label, msg)
    else: 
        if current_loader is not None:
            current_loader.destroy()
            current_loader = None
        label = tk.Label(
            message_frame,
            text=msg,
            bg='red',
            fg='white',
            font=('Arial', 15),
            wraplength=current_wraplength,
            justify='left',
            padx=10,
            pady=10
        )
        label.pack(anchor='w', pady=5, padx=10)
        label.bind("<Button-1>", lambda e: root.focus_set())

    label.bind("<MouseWheel>", on_mousewheel)
    canvas.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox('all'))
    canvas.bind("<Button-1>", lambda e: root.focus_set())
    canvas.yview_moveto(1)
    update_nexabot()  

def animate_typing(label, full_text, typing_speed=0):
    global current_animation_id, stop_requested, current_label, auto_scroll_enabled, is_animating
    current_label = label
    stop_requested = False
    auto_scroll_enabled = True
    is_animating = True

    processed_lines = process_message(full_text)
    current_line_index = 0
    current_char_index = 0

    label.config(state='normal')  

    def type_char():
        nonlocal current_line_index, current_char_index
        global current_animation_id, stop_requested, is_animating
        send_button.pack_forget()
        stop_button.pack(side=tk.RIGHT, padx=5, pady=(0,5))

        if stop_requested or current_line_index >= len(processed_lines):
            label.config(state='disabled')
            stop_button.pack_forget()
            send_button.pack_forget()
            is_animating = False
            
            max_length = max(len(line) for line in processed_lines) if processed_lines else 0
            label.config(
                width=min(max_length, 60),
                height=len(processed_lines)
            )
            return

        current_line = processed_lines[current_line_index]
        if current_char_index < len(current_line):
            label.insert(tk.END, current_line[current_char_index])
            current_char_index += 1
        else:
            label.insert(tk.END, '\n')
            current_line_index += 1
            current_char_index = 0
            
            lines_so_far = processed_lines[:current_line_index]
            current_max = max(len(line) for line in lines_so_far) if lines_so_far else 0
            label.config(
                width=min(current_max, 60),
                height=current_line_index + 1
            )

        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox('all'))
        if auto_scroll_enabled:
            canvas.yview_moveto(1)
        current_animation_id = label.after(typing_speed, type_char)

    type_char()

def send_message(e=None):
    global is_processing, stop_requested, is_animating
    if is_processing or is_animating:
        return
    
    stop_requested = False
    send_button.pack_forget()
    stop_button.pack(side=tk.RIGHT, padx=5, pady=(0,5))
    user_message = user_input.get("1.0", "end-1c").strip()

    if not user_message or user_message == placeholder:
        send_button.pack_forget()
        return
    
    user_input.delete("1.0", tk.END)
    adjust_input_height()
    toggle_send_button() 
    insert_message(f"{user_message}", "user")
   
    threading.Thread(target=get_gemini_response, args=(user_message,)).start()

def get_gemini_response(user_message):
    global is_processing, stop_requested
    try:
        is_processing = True
        response = chat.send_message(user_message)
        cleaned_response = clean_and_format_text(response.text)  
        
        if not stop_requested and app_running:  
            root.after(0, lambda: insert_message(cleaned_response, "bot"))  
    except Exception as e:
        if not stop_requested and app_running: 
            root.after(0, lambda: insert_message(f"Error: {str(e)}", "error"))
    finally:
        if app_running:  
            is_processing = False
            stop_requested = False
            root.after(0, toggle_send_button)
            root.after(0, lambda: stop_button.pack_forget())

def on_mousewheel(event):
    if platform.startswith("linux"):
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
    else:
        canvas.yview_scroll(-1 * (event.delta // 120), "units")

def stop_processing():
    global current_animation_id, is_processing, stop_requested, current_label, is_animating, current_loader
    stop_requested = True
    is_processing = False
    is_animating = False 

    if current_animation_id is not None and current_label is not None and app_running:
        current_label.after_cancel(current_animation_id)
    current_animation_id = None
    current_label = None
    if app_running:  
        stop_button.pack_forget()
        toggle_send_button()
    
    if current_loader is not None:
        current_loader.destroy()
        current_loader = None

def handle_enter(event):
    global is_processing, is_animating
    if is_processing or is_animating: 
        return "break"
    if event.state & 0x1:  
        return  
    send_message()
    return "break"

def on_scroll(*args):
    global auto_scroll_enabled, last_scroll_position
    current_position = canvas.yview()
    if current_position != last_scroll_position:
        auto_scroll_enabled = False
    last_scroll_position = current_position

def periodic_check():
    toggle_send_button()
    root.after(100, periodic_check)

def process_message(text):
    _max_length_ = 60
    processed_lines = []
    for line in text.split('\n'):
        chunks = [line[i:i+_max_length_] for i in range(0, len(line), _max_length_)]
        processed_lines.extend(chunks)
    return processed_lines

def start_selection(event):
    """Begin text selection on click"""
    widget = event.widget
    widget.mark_set("anchor", f"@{event.x},{event.y}")
    widget.tag_remove("sel", "1.0", "end")
    widget.tag_add("sel", "anchor", f"@{event.x},{event.y}")

def extend_selection(event):
    """Update selection while dragging"""
    widget = event.widget
    widget.tag_remove("sel", "1.0", "end")
    widget.tag_add("sel", "anchor", f"@{event.x},{event.y}")

def copy_text(event):
    if event.widget.tag_ranges("sel"):
        event.widget.event_generate("<<Copy>>")
    return "break"

def clean_and_format_text(raw_text):
    text = re.sub(r'`{1,3}python|`{3}', '', raw_text)
    text = re.sub(r'#\s*', '', text)
    text = re.sub(r'\*{1,2}', '', text)
    text = re.sub(r'\n(?=\d+\.\s)', '\n\n', text)
    text = re.sub(r'\n{2,}', '\n\n', text.strip())
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    return '\n'.join(paragraphs)

def handle_key_event(event):
    if event.state & 0x1 and event.keysym in ('Left', 'Right', 'Up', 'Down'):
        return
    return "break"

def load_chat_history(filename):
    global current_chat_title
    save_current_chat()
    filepath =  os.path.join(exe_dir, "chats", filename) 
    try:
        with open(filepath, 'r') as f:
            history_data = json.load(f)
        
        global chat
        chat = model.start_chat(history=[])
        
        for msg in history_data:
            chat.history.append({
                'role': msg['role'],
                'parts': [{'text': '\n'.join(msg['parts'])}]
            })
        
        clear_chat_ui()
        for message in chat.history:
            role = message['role']
            text = message['parts'][0]['text']
            insert_message(text, 'user' if role == 'user' else 'bot')
        
        filename_without_ext = os.path.splitext(filename)[0]
        parts = filename_without_ext.split("_")
        if len(parts) >= 4:
            date_part = parts[1]
            time_part = parts[2].replace("-", ":") + " " + parts[3]
            current_chat_title = f"{date_part} {time_part}"
        else:
            current_chat_title = filename_without_ext.replace("chat_", "")
        
        title_label.config(text=current_chat_title)
        
    except Exception as e:
        if app_running:
            root.after(0, lambda e=e: insert_message(f"Error: {str(e)}", "error"))

def toggle_sidebar():
    global sidebar_shown
    if sidebar_shown:
        animate_hide()
    else:
        animate_show()

def animate_show():
    global sidebar_shown
    current_x = sidebar.winfo_x()
    if current_x < 0:
        new_x = min(0, current_x + 20) 
        sidebar.place(x=new_x, y=0, relheight=1.0)
        update_all_frame_geometry()
        if new_x < 0:
            root.after(3, animate_show)
        else:
            sidebar_shown = True

def animate_hide():
    global sidebar_shown
    current_x = sidebar.winfo_x()
    if current_x > -sidebar_width:
        new_x = max(-sidebar_width, current_x - 20)
        sidebar.place(x=new_x, y=0, relheight=1.0)
        update_all_frame_geometry()
        if new_x > -sidebar_width:
            root.after(10, animate_hide)
        else:
            sidebar_shown = False

def on_resize(event):
    if sidebar_shown:
        sidebar.place_configure(height=root.winfo_height()) 
    update_all_frame_geometry()

def update_all_frame_geometry():
    sidebar_x = sidebar.winfo_x()
    sidebar_width_current = sidebar_width
    all_frame.place(
        x=sidebar_x + sidebar_width_current,
        y=0,
        width=root.winfo_width() - (sidebar_x + sidebar_width_current),
        height=root.winfo_height()
    )

def start_new_chat():
    global chat, current_chat_title, stop_requested, is_processing, is_animating, current_animation_id
    save_current_chat()
    chat = model.start_chat(history=[])
    clear_chat_ui()
    
    stop_requested = True
    is_processing = False
    is_animating = False
    
    if current_animation_id:
        root.after_cancel(current_animation_id)
        current_animation_id = None
    
    stop_button.pack_forget()
    toggle_send_button()
    refresh_sidebar()
    current_chat_title = "New Chat"
    title_label.config(text=current_chat_title)

def save_current_chat():
    global current_chat_title
    if not chat.history:
        return
    
    chat_dir =os.path.join(exe_dir, "chats")  
    if not os.path.exists(chat_dir):
        os.makedirs(chat_dir)
    
    timestamp = datetime.now().strftime("%d-%m-%Y_%I-%M-%S %p")
    
    if current_chat_title and current_chat_title != "New Chat":
        filename = f"chat_{current_chat_title.replace(' ', '_').replace(':', '-')}.json"
    else:
        filename = f"chat_{timestamp}.json"
        current_chat_title = timestamp.replace("_", " ")
    
    filepath = os.path.join(chat_dir, filename)
    
    history = []
    for message in chat.history:
        if isinstance(message, dict):
            role = message['role']
            parts = message['parts']
        else:
            role = message.role
            parts = [part.text for part in message.parts]

        cleaned_parts = []
        for part in parts:
            if isinstance(part, dict):
                cleaned_parts.append(part.get('text', ''))
            else:
                cleaned_parts.append(str(part))

        full_text = '\n'.join(cleaned_parts)
        cleaned_text = clean_and_format_text(full_text)
        
        formatted_lines = []
        for paragraph in cleaned_text.split('\n'):
            formatted_lines.extend([paragraph[i:i+100] for i in range(0, len(paragraph), 100)])
            formatted_lines.append('')
        
        history.append({
            'role': role,
            'parts': [line for line in formatted_lines if line.strip()],
            'timestamp': timestamp
        })
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False, default=str)

def clear_chat_ui():
    for widget in message_frame.winfo_children():
        widget.destroy()
        update_nexabot()  
    
    message_frame.update_idletasks()
    message_frame.config(width=canvas.winfo_width(), height=0)
    
    canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), 1))
    canvas.yview_moveto(0)
    
    canvas.update_idletasks()
    message_frame.update_idletasks()

def refresh_sidebar():
    global new_chat_history_frame, new_chat_history_canvas
    for widget in new_chat_history_frame.winfo_children():
        widget.destroy()
    
    chat_dir = os.path.join(exe_dir, "chats") 
    chat_files = sorted(os.listdir(chat_dir), key=lambda x: os.path.getmtime(os.path.join(chat_dir, x)), reverse=True) if os.path.exists(chat_dir) else []

    cross_img = Image.open(resource_path(r"icons\close.png")).resize((20, 20))
    cross_icon = ImageTk.PhotoImage(cross_img)

    for file_name in chat_files:
        if not file_name.endswith('.json'):
            continue
            
        btn_container = tk.Frame(new_chat_history_frame,width=10, bg=dark_gray)
        btn_container.pack(padx=5, pady=2)

        btn = tk.Button(
            btn_container,
            text=os.path.splitext(file_name)[0].replace("chat_", "").replace("_", " "),
            bg="#606060",
            fg="white",
            font=("Arial", 10),
            anchor="w",
            relief="flat",
            width=21,
            wraplength=170,
            command=lambda f=file_name: load_chat_history(f)
        )
        btn.pack(side=tk.LEFT,expand=True)

        delete_btn = tk.Button(
            btn_container,
            image=cross_icon,
            bg="#606060",
            activebackground="#606060",
            relief="flat",
            command=lambda f=file_name: delete_chat_history(f)
        )
        delete_btn.image = cross_icon  
        delete_btn.pack(side=tk.RIGHT, padx=(2,0))

        btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#707070"))
        btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#606060"))
        delete_btn.bind("<Enter>", lambda e, b=delete_btn: b.config(bg="#ff4444"))
        delete_btn.bind("<Leave>", lambda e, b=delete_btn: b.config(bg="#606060"))

    new_chat_history_canvas.update_idletasks()
    new_chat_history_canvas.configure(scrollregion=new_chat_history_canvas.bbox("all"))

def delete_chat_history(filename):
    filepath = os.path.join(exe_dir, "chats", filename)
    
    try:
        if os.path.exists(filepath):
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {filename}?"):
                os.remove(filepath)
            if current_chat_title in filename:
                start_new_chat()
            refresh_sidebar()
    except Exception as e:
        insert_message(f"Delete error: {str(e)}", "error")

def update_nexabot():
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()
    canvas.coords(nexabot_id, canvas_width/2, canvas_height/2)
    if len(message_frame.winfo_children()) > 0:
        canvas.itemconfigure(nexabot_id, fill="#2a2a2a")  
    else:
        canvas.itemconfigure(nexabot_id, fill="#787878") 

def toggle_send_button():
    current_text = user_input.get("1.0", "end-1c").strip()
    is_placeholder = (user_input.tag_ranges("placeholder") and 
                     current_text == placeholder.strip())
    
    if is_processing:
        send_button.pack_forget()
    elif current_text and not is_placeholder:
        send_button.pack(side=tk.RIGHT, padx=5, pady=(0,5))
    else:
        send_button.pack_forget()

def add_placeholder():
    if not user_input.get("1.0", "end-1c").strip():
        user_input.insert("1.0", placeholder, "placeholder")
        user_input.mark_set("insert", "1.0")
    toggle_send_button() 

def side_bar_btn_with_canvas():
    global sidebar, chat_history_canvas, setting_canvas, help_canvas, chat_history_frame, chat_history_scrollbar, new_chat_history_frame, new_chat_history_canvas

    def slide_canvas(canvas, visible_flag_name, steps=10):
        visible = globals()[visible_flag_name]
        step_size = root.winfo_height() // steps
        delay = 25

        def expand(step=0):
            if step <= steps:
                new_height = step * step_size
                canvas.config(height=new_height)
                root.after(delay, expand, step + 1)
            else:
                globals()[visible_flag_name] = True

        def collapse(step=0):
            if step <= steps:
                new_height = root.winfo_height() - (step * step_size)
                canvas.config(height=max(0, new_height))
                root.after(delay, collapse, step + 1)
            else:
                canvas.config(height=0)
                globals()[visible_flag_name] = False

        if not visible:
            expand()
        else:
            collapse()

    def toggle_canvas1():
        slide_canvas(chat_history_canvas, 'canvas1_visible')

    def toggle_canvas2():
        slide_canvas(setting_canvas, 'canvas2_visible')

    def toggle_canvas3():
        slide_canvas(help_canvas, 'canvas3_visible')

    history_btn = tk.Button(sidebar, text="History", bg="#3a3a3a", fg="white", border=0,highlightthickness=0, 
                            relief="flat", anchor="center", font=("Arial", 12), width=26,
                            command=toggle_canvas1)
    history_btn.pack(pady=(10,2),padx=5, anchor='w')

    global chat_history_canvas
    chat_history_canvas = tk.Canvas(sidebar, height=0, width=234, bg=dark_gray, border=1, highlightthickness=1)
    chat_history_canvas.pack(pady=0, padx=5, anchor='w')

    chat_history_frame = tk.Frame(chat_history_canvas, bg=dark_gray, relief="flat", border=0, highlightthickness=0)
    chat_history_window = chat_history_canvas.create_window((5, 5), window=chat_history_frame, anchor="nw")

    new_chat_history_canvas = tk.Canvas(chat_history_frame, bg=dark_gray, highlightthickness=0)

    chat_history_scrollbar = ttk.Scrollbar(chat_history_frame, orient=tk.VERTICAL, command=new_chat_history_canvas.yview)
    chat_history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    new_chat_history_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    new_chat_history_canvas.configure(yscrollcommand=chat_history_scrollbar.set)
    new_chat_history_canvas.bind("<Configure>", lambda e: new_chat_history_canvas.configure(scrollregion=new_chat_history_canvas.bbox("all"), width=e.width))

    new_chat_history_frame = tk.Frame(new_chat_history_canvas, bg=dark_gray)
    new_chat_history_canvas.create_window((0, 0), window=new_chat_history_frame, anchor="nw")

    new_chat_history_frame.bind("<Configure>", lambda e: new_chat_history_canvas.configure(scrollregion=new_chat_history_canvas.bbox("all")))

    def resize_frame(event):
        canvas_width = event.width
        canvas_height = event.height
        frame_width = max(0, canvas_width - 10)   
        frame_height = max(0, canvas_height - 10)
        chat_history_canvas.itemconfig(chat_history_window, width=frame_width, height=frame_height)

    chat_history_canvas.bind("<Configure>", resize_frame)

    refresh_sidebar()

    def on_mousewheel(event):
        if platform.startswith("linux"):
            if event.num == 4:
                new_chat_history_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                new_chat_history_canvas.yview_scroll(1, "units")
        else:
            new_chat_history_canvas.yview_scroll(-1 * (event.delta // 120), "units")

    new_chat_history_canvas.bind("<MouseWheel>", on_mousewheel)
    new_chat_history_canvas.bind("<Button-4>", on_mousewheel)
    new_chat_history_canvas.bind("<Button-5>", on_mousewheel)
    
    new_chat_history_frame.bind("<MouseWheel>", on_mousewheel)
    new_chat_history_frame.bind("<Button-4>", on_mousewheel)
    new_chat_history_frame.bind("<Button-5>", on_mousewheel)






    setting_btn = tk.Button(sidebar, text="Settings", bg="#3a3a3a", fg="white", border=0,highlightthickness=0, 
                            relief="flat", anchor="center", font=("Arial", 12), width=26,
                            command=toggle_canvas2)
    setting_btn.pack(pady=(2,2),padx=5, anchor='w')

    setting_canvas = tk.Canvas(sidebar, height=0,width=234, bg=dark_gray, border=1,highlightthickness=1)
    setting_canvas.pack(pady=0,padx=5, anchor='w')

    help_btn = tk.Button(sidebar, text="Help", bg="#3a3a3a", fg="white", border=0,highlightthickness=0, 
                            relief="flat", anchor="center", font=("Arial", 12), width=26,
                            command=toggle_canvas3)
    help_btn.pack(pady=(2,2),padx=5, anchor='w')

    help_canvas = tk.Canvas(sidebar, height=0,width=234, bg=dark_gray, border=1,highlightthickness=1)
    help_canvas.pack(pady=0,padx=5, anchor='w')
    

















root = tk.Tk()
root.title("GenieTalk AI")
root.geometry("1200x700")
root.configure(bg="#1a1a1a")

try:
    root.iconbitmap(resource_path(r"icons/icon.ico"))
except Exception as e:
    print("Icon load error:", e) 

style = ttk.Style()
style.theme_use("default")
style.configure("Vertical.TScrollbar",
                gripcount=0,
                background="#787878",
                troughcolor="#3a3a3a",
                bordercolor="#3a3a3a",
                arrowcolor="white",
                width=12)
style.map("Vertical.TScrollbar",
          background=[("active", "#5a5a5a"), ("pressed", "#4a4a4a")])

style.configure("History.TFrame", background=dark_gray)

sidebar = tk.Frame(root, bg="#2d2d2d", width=sidebar_width, height=root.winfo_height())
sidebar.place(x=-sidebar_width, y=0, relheight=1.0, anchor='nw')

all_frame = tk.Frame(root, bg="#1a1a1a")
all_frame.place(x=0, y=0, width=root.winfo_width(), height=root.winfo_height())

top_frame = tk.Frame(all_frame, bg="#1a1a1a")
top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

toggle_button = tk.Button(all_frame, text="☰", font=("Arial", 16), bg="#333", fg="white",border=1,
                          command=toggle_sidebar, relief="flat")

new_chat_img = Image.open(resource_path(r"icons\new_chat.png")).resize((34, 34))
new_chat_icon = ImageTk.PhotoImage(new_chat_img)

new_chat_button = tk.Button(all_frame, image=new_chat_icon, font=("Arial", 10),
                             bg="#1a1a1a", 
                             fg="white",border=0, activebackground="#1a1a1a",
                          command=start_new_chat, relief="flat")

title_label = tk.Label(
    top_frame,
    text="New Chat",
    fg="white",
    bg="#1a1a1a",
    font=("Arial", 12, "bold")
)
toggle_button.pack(in_=top_frame, side=tk.LEFT, padx=10)
title_label.pack(in_=top_frame, side=tk.LEFT, expand=True, fill=tk.X, padx=10)
new_chat_button.pack(in_=top_frame, side=tk.RIGHT, padx=10)

frame = tk.Frame(all_frame, bg="#1a1a1a")
frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 0))

canvas = tk.Canvas(frame, bg="#2a2a2a", highlightthickness=0)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
nexabot_id = canvas.create_text(0, 0, text="GenieTalk", font=("Arial", 60, "bold"), fill="#787878", anchor=tk.CENTER, tags="nexabot")

scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=lambda *args: [canvas.yview(*args), on_scroll()], style="Vertical.TScrollbar")
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

canvas.configure(yscrollcommand=scrollbar.set)

message_frame = tk.Frame(canvas, bg="#2a2a2a")
window_id = canvas.create_window((0, 0), window=message_frame, anchor='nw')
message_frame.bind("<Button-1>", lambda e: root.focus_set())
message_frame.bind("<Configure>", on_message_frame_configure)

canvas.bind("<Configure>", on_canvas_configure)
canvas.bind("<Button-1>", lambda e: root.focus_set())

input_frame = tk.Frame(all_frame, bg="#1a1a1a")
input_frame.pack(fill=tk.X, padx=10, pady=10)

text_container = tk.Frame(input_frame, bg="#1a1a1a")
text_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

text_scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, style="Vertical.TScrollbar")

user_input = tk.Text(
    text_container,
    height=4,
    font=("Arial", 14),
    bg="#333",
    fg="white",
    width=100,
    insertbackground="white",
    wrap="word",
    padx=20,
    pady=20,
    yscrollcommand=text_scrollbar.set,
    relief="flat"
)
user_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

user_input.tag_configure("placeholder", foreground="#666666", font=('Arial', 18, 'bold'))

user_input.bind("<KeyRelease>", lambda e: adjust_input_height())
user_input.bind("<KeyPress>", lambda e: adjust_input_height())
user_input.bind("<FocusIn>", on_focusin)
user_input.bind("<FocusOut>", on_focusout)
user_input.unbind("<Return>")
user_input.bind("<Return>", handle_enter)

text_scrollbar.config(command=user_input.yview)
user_input.config(yscrollcommand=text_scrollbar.set)

btn_frame = tk.Frame(input_frame,
                      height=37,
                      bg="#333"
                      )
btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

upload_img = Image.open(resource_path(r"icons\upload.png")).resize((30, 30))
upload_icon = ImageTk.PhotoImage(upload_img)

stop_img = Image.open(resource_path(r"icons\stop.png")).resize((30, 30))
stop_icon = ImageTk.PhotoImage(stop_img)

send_button = tk.Button(
    btn_frame,
    image=upload_icon,
    font=("Arial", 12, "bold"),
    bg="#333",
    fg="white",
    activebackground="#333",
    command=send_message,
    relief="flat",
    padx=20,
    pady=10,
    border=0,
    borderwidth=0
)

stop_button = tk.Button(
    btn_frame,
    image=stop_icon,
    font=("Arial", 12, "bold"),
    bg="#333",
    fg="white",
    activebackground="#333",
    relief="flat",
    padx=20,
    pady=10,
    command=stop_processing ,
    border=0,
    borderwidth=0
)

if platform.startswith("linux"):
    canvas.bind("<Button-4>", on_mousewheel)
    canvas.bind("<Button-5>", on_mousewheel)
    message_frame.bind("<Button-4>", on_mousewheel)
    message_frame.bind("<Button-5>", on_mousewheel)
    
else:
    canvas.bind("<MouseWheel>", on_mousewheel)
    message_frame.bind("<MouseWheel>", on_mousewheel)


load_window_geometry()
side_bar_btn_with_canvas()
update_nexabot()
root.bind('<Configure>', track_geometry)
root.protocol("WM_DELETE_WINDOW", on_close)
add_placeholder()
root.after(100, periodic_check)
root.after(1, save_current_chat)
root.after(100, animate_show) 
root.bind("<Configure>", on_resize)
root.bind("<Configure>", lambda e: update_all_frame_geometry())
root.mainloop()












