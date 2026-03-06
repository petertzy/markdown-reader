import os
import re
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from markdown_reader.logic import update_preview
from markdown_reader.logic import open_preview_in_browser
from markdown_reader.logic import export_to_html
from markdown_reader.logic import export_to_docx
from markdown_reader.logic import export_to_pdf
from markdown_reader.logic import convert_html_to_markdown
from markdown_reader.logic import convert_pdf_to_markdown
from markdown_reader.logic import convert_pdf_to_markdown_docling
from markdown_reader.logic import translate_markdown_with_ai
from markdown_reader.file_handler import load_file, drop_file
from markdown_reader.utils import get_preview_file
import tkinter.font  # moved here from inside methods
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from ttkbootstrap import dialogs
import markdown
from .plugins.pdf_exporter import export_markdown_to_pdf


class FileChangeHandler(FileSystemEventHandler):
    """
    The class that handles changes to files.

    :param FileSystemEventHandler: The file system event handler from the watchdog.events library.
    """
    
    def __init__(self, app, filepath):
        """
        :param MarkdownReader app: The instance of the MarkdownReader application.
        :param string filepath: The file path for the file to be monitored.
        """

        self.app = app
        self.filepath = os.path.abspath(filepath)

    def on_modified(self, event):
        """
        When the file is modified, reload the file after 100ms.

        :param event event: The file modification event. 
        """
        
        if os.path.abspath(event.src_path) == self.filepath:
            self.app.root.after(100, lambda: self.app.load_file(self.filepath))


class MarkdownReader:
    """
    The class that creates the instance of the Markdown reader application.
    """
    
    def __init__(self, root):
        """
        :param TkinterDnD.Tk root: The window that the application uses as a display.
        """
        
        self.root = root
        self.root.title("Markdown Reader")
        self.root.geometry("1280x795")
        
        # Enable window resizing - force both width and height to be resizable
        self.root.resizable(width=True, height=True)
        # Set minimum window size to prevent it from being too small
        self.root.minsize(800, 600)
        
        self.dark_mode = False
        self.preview_file = get_preview_file()
        self.current_file_path = None
        self.observer = None

        # --- Toolbar state ---
        self.current_font_family = "Consolas"
        self.current_font_size = 14
        self.current_fg_color = "#000000"
        self.current_bg_color = "#ffffff"
        
        # Flag to prevent marking as modified during file loading
        self._loading_file = False
        
        # Track which tabs have unsaved modifications
        self.modified_tabs = set()
        
        # PDF conversion mode: False = PyMuPDF (fast), True = Docling (advanced)
        self.use_docling_pdf = False
        
        # IME state tracking per widget
        self._ime_states = {}

        # Translation defaults
        self.translation_source_language = "English"
        self.translation_target_language = "German"
        self.translation_languages = [
            "English",
            "Japanese",
            "Korean",
            "German",
            "French",
            "Spanish",
            "Italian",
            "Portuguese",
            "Russian",
            "Arabic",
            "Hindi",
            "Dutch",
            "Swedish",
            "Polish",
            "Turkish",
            "Vietnamese",
            "Thai",
            "Indonesian",
            "Chinese (Simplified)",
            "Chinese (Traditional)",
        ]
        self.ai_provider_var = tk.StringVar(value=os.getenv("AI_PROVIDER", "openrouter").strip().lower() or "openrouter")

        self.create_widgets()
        self.bind_events()


    def create_widgets(self):
        """
        Sets up the various menus, toolbar, and fonts.
        """
        
        style = ttkb.Style()
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_file)
        filemenu.add_command(label="Open File", command=self.open_file)
        filemenu.add_command(label="Save File", command=self.save_file)
        filemenu.add_separator()
        filemenu.add_command(label="Export to HTML", command=self.export_to_html_dialog)
        filemenu.add_command(label="Export to Word", command=self.export_to_docx_dialog)
        filemenu.add_command(label="Export to PDF", command=self.export_to_pdf_dialog)
        filemenu.add_separator()
        filemenu.add_command(label="Close", command=self.close_current_tab)
        filemenu.add_command(label="Close All", command=self.close_all_tabs)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        viewmenu.add_command(label="Open Preview in Browser",
                             command=lambda: open_preview_in_browser(self.preview_file, self))
        menubar.add_cascade(label="View", menu=viewmenu)

        editmenu = ttkb.Menu(menubar, tearoff=0)
        editmenu.add_command(label="Undo", command=self.undo_action)
        editmenu.add_command(label="Redo", command=self.redo_action)
        editmenu.add_separator()
        translatemenu = tk.Menu(editmenu, tearoff=0)
        translatemenu.add_command(
            label="Translate Selected Text with AI",
            command=lambda: self.translate_with_ai(selected_only=True)
        )
        translatemenu.add_command(
            label="Translate Full Document with AI",
            command=lambda: self.translate_with_ai(selected_only=False)
        )
        editmenu.add_cascade(label="Translate with AI", menu=translatemenu)
        menubar.add_cascade(label="Edit", menu=editmenu)

        settingsmenu = tk.Menu(menubar, tearoff=0)
        provider_menu = tk.Menu(settingsmenu, tearoff=0)
        provider_menu.add_radiobutton(
            label="OpenRouter",
            variable=self.ai_provider_var,
            value="openrouter",
            command=lambda: self.set_ai_provider("openrouter"),
        )
        provider_menu.add_radiobutton(
            label="OpenAI",
            variable=self.ai_provider_var,
            value="openai",
            command=lambda: self.set_ai_provider("openai"),
        )
        provider_menu.add_radiobutton(
            label="Anthropic",
            variable=self.ai_provider_var,
            value="anthropic",
            command=lambda: self.set_ai_provider("anthropic"),
        )
        settingsmenu.add_cascade(label="AI Provider", menu=provider_menu)
        menubar.add_cascade(label="Settings", menu=settingsmenu)

        # Tools menu with PDF conversion options
        toolsmenu = tk.Menu(menubar, tearoff=0)
        self.pdf_mode_var = tk.BooleanVar(value=self.use_docling_pdf)
        toolsmenu.add_checkbutton(
            label="Use Advanced PDF Conversion (Docling)",
            variable=self.pdf_mode_var,
            command=self.toggle_pdf_mode
        )
        toolsmenu.add_separator()
        toolsmenu.add_command(label="PDF Converter Info", command=self.show_pdf_converter_info)
        menubar.add_cascade(label="Tools", menu=toolsmenu)

        # ADD THIS NEW BLOCK:
        tablemenu = tk.Menu(menubar, tearoff=0)
        tablemenu.add_command(label="Insert Table...", command=self.insert_table)
        tablemenu.add_separator()
        tablemenu.add_command(label="Table Syntax Help", command=self.show_table_help)
        menubar.add_cascade(label="Table", menu=tablemenu)
     
        self.root.config(menu=menubar)

        # --- Toolbar ---
        style.configure('primary.TFrame')
        toolbar = ttkb.Frame(self.root, relief=tk.RAISED, style='primary.TFrame', padding=(5, 5, 0, 5))
        # Style dropdown
        self.style_var = tk.StringVar(value="Normal text")
        style_options = ["Normal text", "Heading 1", "Heading 2", "Heading 3"]
        style.configure('info.Outline.TMenubutton')
        # style_menu = tk.OptionMenu(toolbar, self.style_var, *style_options, command=self.apply_style)
        style_menu = ttkb.Menubutton(toolbar, textvariable=self.style_var, style='info.Outline.TMenubutton')
        style_menu.config(width=12)
        style_menu.pack(side=tk.LEFT, padx=2, pady=2)
        menu_ = tk.Menu(style_menu, tearoff=0)
        for s in style_options:
            menu_.add_radiobutton(label=s, variable=self.style_var, command=lambda s=s: self.apply_style(s))
        style_menu['menu'] = menu_
        # Font family dropdown
        fonts = sorted(set(tkinter.font.families()))
        self.font_var = ttkb.StringVar(value="Consolas")
        font_menu = ttkb.Menubutton(toolbar, textvariable=self.font_var, style='info.Outline.TMenubutton')
        
        font_menu.config(width=10)
        font_menu.pack(side=tk.LEFT, padx=2)
        
        menu = tk.Menu(font_menu, tearoff=0)
        for f in fonts[:20]:
            menu.add_radiobutton(label=f, variable=self.font_var, command=lambda f=f: self.apply_font(f))
        font_menu['menu'] = menu
        # Font size
        self.font_size_var = tk.IntVar(value=14)
        button_width = 3
        uniform_padding = (5, 4)
        # entry config
        style.configure('info.TEntry')
        ttkb.Button(toolbar, text="-", bootstyle=(DANGER, OUTLINE), width=button_width,padding=uniform_padding, command=lambda: self.change_font_size(-1)).pack(side=tk.LEFT, padx = 5)
        ttkb.Entry(toolbar, textvariable=self.font_size_var, width=3, style='info.TEntry', justify='center').pack(side=tk.LEFT)
        ttkb.Button(toolbar, text="+", bootstyle=(SUCCESS, OUTLINE), width=button_width,padding=uniform_padding, command=lambda: self.change_font_size(1)).pack(side=tk.LEFT, padx=5)

        # font configuration
        
        # toggle bold
        style.configure('bold.info.TButton', font=("Arial", 9, "bold"), padding=uniform_padding)
        # toggle italic
        style.configure('italic.info.TButton', font=("Arial", 9, "italic"), padding=uniform_padding)
        # toggle underline
        style.configure('underline.info.TButton', font=("Arial", 9, "underline"), padding=uniform_padding)
        # insert table
        style.configure('insert.info.TButton', font=("Arial", 9), padding=uniform_padding)
        # choose fg color
        style.configure('fg.info.TButton', font=("Arial", 9), padding=uniform_padding)
        # highlight
        style.configure('bg.info.TButton', font=("Arial", 9), padding=uniform_padding)

        ttkb.Button(toolbar, text="B", style='bold.info.TButton', width=button_width, command=self.toggle_bold).pack(side=tk.LEFT, padx=5)
        ttkb.Button(toolbar, text="I", style='italic.info.TButton', width=button_width, command=self.toggle_italic).pack(side=tk.LEFT, padx=5)
        ttkb.Button(toolbar, text="U", style='underline.info.TButton', width=button_width, command=self.toggle_underline).pack(side=tk.LEFT, padx=5)
        ttkb.Button(toolbar, text="⊞", style='insert.info.TButton',width=button_width, command=self.insert_table).pack(side=tk.LEFT, padx=5)
        # Text color
        ttkb.Button(toolbar, text="A", style='fg.info.TButton', width=button_width, command=self.choose_fg_color).pack(side=tk.LEFT, padx=5)
        # Highlight color
        ttkb.Button(toolbar, text="\u0332", style='bg.info.TButton', width=button_width, command=self.choose_bg_color).pack(side=tk.LEFT, padx=5)
        toolbar.pack(fill=tk.X)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.editors = []
        self.file_paths = []
        
        # Create context menu for tabs
        self.tab_context_menu = tk.Menu(self.root, tearoff=0)
        self.tab_context_menu.add_command(label="Close", command=self.close_tab_from_context_menu)
        
        # Bind click event to detect close button clicks
        self.notebook.bind("<Button-1>", self.on_tab_click)
        
        # Bind right-click for context menu
        self.notebook.bind("<Button-2>" if self.root.tk.call('tk', 'windowingsystem') == 'aqua' else "<Button-3>", self.show_tab_context_menu)

        self.new_file()


    def bind_events(self):
        """
        Sets up drag-and-drop support alongside key binds for shortcuts.

        :raises RuntimeError: If the drag-and-drop binding fails.
        """
        
        try:
            # Register drag-and-drop support
            self.root.drop_target_register('DND_Files')
            self.root.dnd_bind('<<Drop>>', self._on_drop_files)
            print("✅ Drag-and-drop support enabled")
        except Exception as e:
            print(f"⚠️  Drag-and-drop binding failed: {e}")

        # Keyboard shortcuts
        self.root.bind_all("<Control-s>", lambda event: self.save_file())
        self.root.bind_all("<Command-s>", lambda event: self.save_file())
        self.root.bind_all("<Control-z>", lambda event: self.undo_action())
        self.root.bind_all("<Control-y>", lambda event: self.redo_action())
        self.root.bind_all("<Control-Shift-T>", lambda event: self.translate_with_ai(selected_only=False))
        self.root.bind_all("<Control-n>", lambda event: self.new_file())
        self.root.bind_all("<Command-z>", lambda event: self.undo_action())
        self.root.bind_all("<Command-Shift-Z>", lambda event: self.redo_action())
        self.root.bind_all("<Command-Shift-T>", lambda event: self.translate_with_ai(selected_only=False))


    def _on_drop_files(self, event):
        """
        Handles file drop events.

        :param event event: The file drop event to be processed.

        :raises RuntimeError: If the error handling drop fails.
        """

        print(f"🔍 Drop event triggered")
        print(f"   Event data type: {type(event.data)}")
        print(f"   Event data: {event.data}")
        
        try:
            drop_file(event, self)
        except Exception as e:
            print(f"❌ Error handling drop: {e}")
            import traceback 
            traceback.print_exc()


    def new_file(self):
        """
        Handles opening a new file and deals with relevant IME files.
        """
        
        frame = tk.Frame(self.notebook)
        base_font = (self.current_font_family, self.current_font_size)
        text_area = self.get_current_text_area()
        text_area = ScrolledText(frame, wrap=tk.WORD, font=base_font, undo=True)
        text_area.pack(fill=tk.BOTH, expand=True)

        # Zoom bindings must be widget-level (not bind_all) so "break" can
        # suppress the Text class's built-in scroll and scan-drag handlers.
        text_area.bind("<MouseWheel>", self._on_ctrl_scroll)
        text_area.bind("<Button-4>", self._on_linux_scroll)
        text_area.bind("<Button-5>", self._on_linux_scroll)
        text_area.bind("<Button-2>", self._on_middle_press)
        text_area.bind("<B2-Motion>", self._on_middle_drag)
        text_area.bind("<ButtonRelease-2>", self._on_middle_release)

        # Setup IME interception
        wid = str(text_area)
        self._ime_states[wid] = {'active': False}
        
        def intercept_key(event):
            """ 
            Detects when a key has been pressed and updates the document accordingly.
            
            :param event event: The keypress event.

            :return: A None value.
            """

            state = self._ime_states[wid]
            
            # Detect IME activation (macOS IME emits empty char with keycode 0)
            if event.char == '' and event.keycode == 0:
                state['active'] = True
                return None

            # Deletion should mark modified but must not toggle IME state
            if event.keysym in ('BackSpace', 'Delete'):
                if not self._loading_file:
                    try:
                        idx = self.notebook.index(self.notebook.select())
                        self.mark_tab_modified(idx)
                    except:
                        pass
                return None
            
            # Detect IME deactivation (non-ASCII = committed text)
            if event.char and ord(event.char) > 127:
                state['active'] = False
                # Mark tab as modified when committed Japanese text arrives
                if not self._loading_file:
                    try:
                        idx = self.notebook.index(self.notebook.select())
                        self.mark_tab_modified(idx)
                    except:
                        pass
                return None
            
            # For lowercase ASCII letters during IME, delete them immediately
            if state['active'] and event.char:
                if event.char.islower() and event.char.isalpha():
                    # Delete with highest priority (0 delay)
                    text_area.after(0, lambda: delete_ime_char())
            # For regular (non-IME) text input, mark as modified
            elif event.char and not state['active']:
                if not self._loading_file:
                    try:
                        idx = self.notebook.index(self.notebook.select())
                        self.mark_tab_modified(idx)
                    except:
                        pass
            
            return None
        
        def delete_ime_char():
            """
            Takes the most recently inserted character, and if its a lowercase letter (IME composition character), delete it.
            """
            
            try:
                # Get current cursor position
                current_index = text_area.index('insert')
                # Calculate previous position
                line, col = current_index.split('.')
                prev_col = int(col) - 1
                if prev_col >= 0:
                    prev_index = f"{line}.{prev_col}"
                    # Get the character that was just inserted
                    char = text_area.get(prev_index, current_index)
                    # Delete it if it's a lowercase letter (IME composition character)
                    if char and len(char) == 1 and char.islower() and char.isalpha():
                        text_area.delete(prev_index, current_index)
            except Exception:
                pass
        
        # Bind KeyPress DIRECTLY with priority
        text_area.bind('<KeyPress>', intercept_key, add=False)
        
        # Other bindings come after
        self.notebook.add(frame, text="")
        tab_index = len(self.editors)
        self.notebook.select(tab_index)
        self.editors.append(text_area)
        self.file_paths.append(None)
        
        # Add custom tab with close button
        self.add_label_and_close_button_to_tab(tab_index, "Untitled")


    def open_file(self):
        """
        Handles opening a file and sets up its file handler.
        """

        file_path = filedialog.askopenfilename(filetypes=[
            ("Markdown files", "*.md *.MD"),
            ("HTML files", "*.html *.HTML *.htm *.HTM"),
            ("PDF files", "*.pdf *.PDF"),
            ("All files", "*.*")
        ])
        if file_path and (file_path.lower().endswith(".md") or file_path.lower().endswith((".html", ".htm", ".pdf"))):
            abs_path = os.path.abspath(file_path)
            self.md_filepath_list = []
            self.md_filepath_list.append(abs_path)
            if abs_path in self.file_paths:
                index = self.file_paths.index(abs_path)
                self.notebook.select(index)
                self.load_file(abs_path)
                self.start_watching(abs_path)
                return

            self.new_file()
            self.load_file(abs_path)
            self.start_watching(abs_path)


    def load_file(self, path):
        """
        Loads the file from the given path and converts it to Markdown.

        :param string path: The path for the file to load.

        :raises RuntimeError: If the file fails to load.
        """
        
        abs_path = os.path.abspath(path)
        idx = self.notebook.index(self.notebook.select())
        text_area = self.get_current_text_area()
        is_html = abs_path.lower().endswith((".html", ".htm"))
        is_pdf = abs_path.lower().endswith(".pdf")

        try:
            # Set loading flag to prevent marking as modified
            self._loading_file = True
            
            # Check if file is PDF and convert to Markdown
            if is_pdf:
                if self.use_docling_pdf:
                    content = convert_pdf_to_markdown_docling(abs_path)
                else:
                    content = convert_pdf_to_markdown(abs_path)
            else:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Check if file is HTML and convert to Markdown
                if is_html:
                    content = convert_html_to_markdown(content)
            
            # Clear the text area and insert new content
            text_area.delete("1.0", tk.END)
            text_area.insert(tk.END, content)
            
            # Reset the modified flag
            text_area.edit_modified(False)
            
            # Update tab info and save state
            if is_html or is_pdf:
                # Update tab name to show it's converted
                base_name = os.path.splitext(os.path.basename(abs_path))[0]
                tab_text = f"{base_name}.md (converted)"
                self.add_label_and_close_button_to_tab(idx, tab_text)
                # Don't set file_paths to HTML/PDF file - treat as new unsaved file
                self.file_paths[idx] = None
                self.current_file_path = None
            else:
                self.file_paths[idx] = abs_path
                tab_text = os.path.basename(abs_path)
                self.add_label_and_close_button_to_tab(idx, tab_text)
                self.current_file_path = abs_path
        except Exception as e:
            dialogs.Messagebox.show_error("Error", f"Failed to load file: {e}")
        finally:
            # Always clear the loading flag first
            self._loading_file = False
            
            # Delay marking tab state to ensure all events are processed
            # Use after_idle to run after all pending events in the queue
            if is_html or is_pdf:
                # Mark as modified since it's converted content
                self.root.after(100, lambda: self.mark_tab_modified(idx))
            else:
                # Mark as saved since we just loaded from file
                self.root.after(100, lambda: self.mark_tab_saved(idx))


    def close_current_tab(self):
        """
        Closes the current tab and lets the notebook forget it.
        """

        if not self.editors:
            return
        idx = self.notebook.index(self.notebook.select())
        
        # Remove from modified tabs if present
        if idx in self.modified_tabs:
            self.modified_tabs.remove(idx)
        
        # Update indices in modified_tabs for tabs after the closed one
        self.modified_tabs = {i if i < idx else i - 1 for i in self.modified_tabs}
        
        self.notebook.forget(idx)
        del self.editors[idx]
        del self.file_paths[idx]


    def close_all_tabs(self):
        """
        Closes all tabs and empties the notebook.
        """

        while self.editors:
            self.notebook.forget(0)
            del self.editors[0]
            del self.file_paths[0]
        # Clear modified tabs set
        self.modified_tabs.clear()


    def on_tab_click(self, event):
        """
        Handles click events on notebook tabs to detect close button clicks.
        Closes tab when clicking near the × symbol (rightmost area).

        :param event event: The click event to be handled.

        :return: The string "break" if a tab was closed, else does not return anything.
        """

        try:
            # Identify which tab was clicked
            element = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
            if element == "":
                return
            
            tab_index = int(element)
            tab_text = self.notebook.tab(tab_index, "text")
            
            # Only proceed if × is in the tab text
            if "×" not in tab_text:
                return

            # Get the tab's bounding box for x position
            tab_bbox = self.notebook.bbox(tab_index)
            if not tab_bbox:
                return
                
            tab_x = tab_bbox[0]
            relative_x = event.x - tab_x
            
            # Use font to measure actual text width
            import tkinter.font as tkfont
            # Get the default font used by ttk.Notebook tabs
            try:
                # Try to get the actual font from the style
                style = ttk.Style()
                tab_font = tkfont.Font(font=style.lookup('TNotebook.Tab', 'font'))
            except:
                # Fallback to a reasonable default
                tab_font = tkfont.Font(family='TkDefaultFont', size=10)
            
            # Measure the actual width of the tab text
            text_width = tab_font.measure(tab_text)
            # Add padding (tabs usually have padding on both sides)
            tab_padding = 20
            estimated_tab_width = text_width + tab_padding
            
            # The "  ×" part is approximately 20-25 pixels
            # Only close if clicking in the rightmost 30 pixels
            close_button_width = 30
            close_threshold = estimated_tab_width - close_button_width
            
            if relative_x >= close_threshold:
                self.close_tab_by_index(tab_index)
                return "break"  # Prevent default tab selection behavior
                
        except Exception as e:
            print(f"Error in on_tab_click: {e}")
            import traceback
            traceback.print_exc()


    def show_tab_context_menu(self, event):
        """
        Shows the context menu when right-clicking on a tab.

        :param event event: The click event to be handled.

        :raises RuntimeError: If there is an error when attempting to display the context menu.
        """
        
        try:
            # Identify which tab was clicked
            clicked_tab = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
            if clicked_tab != "":
                # Store the clicked tab index for later use
                self.right_clicked_tab_index = int(clicked_tab)
                # Show the context menu at cursor position
                self.tab_context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"Error showing context menu: {e}")
    

    def close_tab_from_context_menu(self):
        """
        Close the tab that was right-clicked.
        """

        if hasattr(self, 'right_clicked_tab_index') and self.right_clicked_tab_index < len(self.editors):
            self.close_tab_by_index(self.right_clicked_tab_index)


    def add_label_and_close_button_to_tab(self, tab_index, tab_text):
        """
        Add a close button (×) to the tab text.
        Note: ttk.Notebook doesn't support embedded widgets, so we use text with click detection.

        :param int tab_index: The index of the tab to add the label and close button to.
        :param string tab_text: The text for the tab label.
        """
        
        # Simply update the tab text with × symbol
        # The on_tab_click handler will detect clicks in the rightmost region
        self.notebook.tab(tab_index, text=f"{tab_text}  ×")
    
    
    def close_tab_by_index(self, idx):
        """
        Closes the tab at the specified index.

        :param int idx: The index of the tab to be closed.
        """
        
        if idx < len(self.editors):
            # Remove from modified tabs if present
            if idx in self.modified_tabs:
                self.modified_tabs.remove(idx)
            
            # Update indices in modified_tabs for tabs after the closed one
            self.modified_tabs = {i if i < idx else i - 1 for i in self.modified_tabs}
            
            self.notebook.forget(idx)
            del self.editors[idx]
            del self.file_paths[idx]
            
            # Update tab_widgets dictionary
            if hasattr(self, 'tab_widgets'):
                # Remove the closed tab
                if idx in self.tab_widgets:
                    del self.tab_widgets[idx]
                # Update indices for remaining tabs
                new_widgets = {}
                for key, value in self.tab_widgets.items():
                    new_key = key if key < idx else key - 1
                    new_widgets[new_key] = value
                self.tab_widgets = new_widgets


    def start_watching(self, path):
        """
        Sets up a watchdog.observers Observer instance to monitor the file for modifications.

        :param string path: The file path for the file to be monitored.
        """
        
        if self.observer:
            self.observer.stop()
            self.observer.join()

        event_handler = FileChangeHandler(self, path)
        self.observer = Observer()
        watch_dir = os.path.dirname(os.path.abspath(path))
        self.observer.schedule(event_handler, path=watch_dir, recursive=False)
        self.observer.start()


    def on_text_change(self):
        """
        When the text is changed, reapply all formatting and update the preview file.
        """
        
        self.highlight_markdown()
        self.update_preview()


    def toggle_dark_mode(self):
        """
        Toggles between light and dark mode.
        """

        self.dark_mode = not self.dark_mode
        bg = "#1e1e1e" if self.dark_mode else "white"
        fg = "#dcdcdc" if self.dark_mode else "black"

        for text_area in self.editors:
            text_area.config(bg=bg, fg=fg, insertbackground=fg)


    def highlight_markdown(self):
        """
        Removes all existing formatting and inserts new tags based on the updated Markdown syntax.
        Implementation in place for:
        - Headings (#, ##, ### ... to 6).
        - Bold or italic text.
        - Links, blockquotes, and inline code.
        - Lists (unordered and ordered).
        - Tables.
        """
        
        # Get the current editor
        text_area = self.get_current_text_area()
        content = text_area.get("1.0", tk.END)

        # Remove all previous tags
        for tag in text_area.tag_names():
            text_area.tag_remove(tag, "1.0", tk.END)

        # Use the selected font for highlighting
        import tkinter.font
        import platform
        system = platform.system()
        if system == "Darwin":          # macOS
            default_font = "Menlo"
        elif system == "Windows":
            default_font = "Consolas"
        else:                           # Linux
            default_font = "Ubuntu Mono"
        font_name = getattr(self, 'current_font_family', default_font)
        font_size = getattr(self, 'current_font_size', 14)
        text_area.tag_configure("heading", foreground="#333333", font=(font_name, font_size + 4, "bold"))
        text_area.tag_configure("bold", font=(font_name, font_size, "bold"))
        text_area.tag_configure("italic", font=(font_name, font_size, "italic"))
        text_area.tag_configure("code", foreground="#d19a66", background="#f6f8fa", font=(font_name, font_size))
        text_area.tag_configure("link", foreground="#2aa198", underline=True)
        text_area.tag_configure("blockquote", foreground="#6a737d", font=(font_name, font_size, "italic"))
        text_area.tag_configure("list", foreground="#b58900", font=(font_name, font_size, "bold"))
        # ADD THIS NEW LINE:
        text_area.tag_configure("table", foreground="#0066cc", font=(font_name, font_size))

        import re
        lines = content.splitlines(keepends=True)
        pos = 0
        for line in lines:
            start_idx = f"{pos + 1}.0"
            end_idx = f"{pos + 1}.end"
            # Headings: #, ##, ### ...
            if re.match(r"^#{1,6} ", line):
                text_area.tag_add("heading", start_idx, end_idx)
            # Blockquotes: >
            if re.match(r"^> ", line):
                text_area.tag_add("blockquote", start_idx, end_idx)
            # Lists: -, *, +, or numbered
            if re.match(r"^\s*([-*+] |\d+\. )", line):
                text_area.tag_add("list", start_idx, end_idx)
            # ADD THIS NEW BLOCK:
            # Table rows: | cell | cell |
            if "|" in line and line.strip().startswith("|"):
                text_area.tag_add("table", start_idx, end_idx)
            # Inline code: `code`
            for m in re.finditer(r"`([^`]+)`", line):
                s = f"{pos + 1}.{m.start()}"
                e = f"{pos + 1}.{m.end()}"
                text_area.tag_add("code", s, e)
            # Bold: **text** or __text__
            for m in re.finditer(r"(\*\*|__)(.*?)\1", line):
                s = f"{pos + 1}.{m.start(2)}"
                e = f"{pos + 1}.{m.end(2)}"
                text_area.tag_add("bold", s, e)
            # Italic: *text* or _text_ (not bold)
            for m in re.finditer(r"(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)|(?<!_)_(?!_)([^_]+)(?<!_)_(?!\*)", line):
                group = 1 if m.group(1) else 2
                s = f"{pos + 1}.{m.start(group)}"
                e = f"{pos + 1}.{m.end(group)}"
                text_area.tag_add("italic", s, e)
            # Links: [text](url)
            for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line):
                s = f"{pos + 1}.{m.start()}"
                e = f"{pos + 1}.{m.end()}"
                text_area.tag_add("link", s, e)
            pos += 1


    def mark_tab_modified(self, tab_index):
        """
        Marks a tab as having unsaved modifications.

        :param int tab_index: The index of the tab to be marked as modified.
        """

        if tab_index not in self.modified_tabs:
            self.modified_tabs.add(tab_index)
            # Get current tab title
            current_title = self.notebook.tab(tab_index, "text")
            # Remove the close button symbol if present
            if current_title.endswith("  ×"):
                current_title = current_title[:-3]
            # Add asterisk if not already present
            if not current_title.startswith("* "):
                self.notebook.tab(tab_index, text=f"* {current_title}  ×")
    

    def mark_tab_saved(self, tab_index):
        """
        Marks a tab as saved and removes the unsaved indicator.
        
        :param int tab_index: The index of the tab to be marked as saved.
        """
        
        if tab_index in self.modified_tabs:
            self.modified_tabs.remove(tab_index)
        # Get current tab title and remove asterisk if present
        try:
            current_title = self.notebook.tab(tab_index, "text")
            # Remove the close button symbol if present
            if current_title.endswith("  ×"):
                current_title = current_title[:-3]
            if current_title.startswith("* "):
                current_title = current_title[2:]
            # Re-add close button
            self.notebook.tab(tab_index, text=f"{current_title}  ×")
        except:
            pass


    def quit(self):
        """
        Stops the file observer if it's running, and then quits the application.
        """

        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.root.quit()


    def save_file(self):
        """
        Saves the current file. If the file has been previously saved, it will overwrite the existing file. If not, the user will be prompted to choose a save location and file name.
        
        :raises RuntimeError: If there is an error saving the file to current_path.
        :raises RuntimeError: If there is an error saving the file to the user-selected path.
        """
        
        text_area = self.get_current_text_area()
        if not text_area:
            return
        idx = self.notebook.index(self.notebook.select())
        current_path = self.file_paths[idx]

        if current_path:
            try:
                content = text_area.get("1.0", "end-1c")
                with open(current_path, "w", encoding="utf-8") as f:
                    f.write(content)
                # Mark tab as saved
                self.mark_tab_saved(idx)
            except Exception as e:
                dialogs.Messagebox.show_error("Error", f"Failed to save file: {e}")
        else:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                initialfile="default.md"
            )
            if file_path:
                try:
                    content = text_area.get("1.0", "end-1c")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.file_paths[idx] = file_path
                    tab_text = os.path.basename(file_path)
                    self.notebook.tab(idx, text=f"{tab_text}  ×")
                    # Mark tab as saved (will ensure no asterisk)
                    self.mark_tab_saved(idx)
                except Exception as e:
                    dialogs.Messagebox.show_error("Error", f"Failed to save file: {e}")


    # --- Toolbar functions ---
    def get_current_text_area(self):
        """
        Returns the current text editor in the active tab.

        :return: The text editor for the active tab, or None if there are no editors.
        """
        
        if not self.editors:
            return None
        idx = self.notebook.index(self.notebook.select())
        return self.editors[idx]


    def apply_style(self, style):
        """
        Applies the heading styles to the relevant lines, or removes the heading if it is normal text, then updates the preview.

        :param string style: The style to be applied, which can be "Heading 1", "Heading 2", or "Heading 3". Any other value will be treated as normal text and will remove heading formatting.
        
        :raises tk.TclError: If there is an error accessing the text area or its contents.
        """
        
        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
        except tk.TclError:
            # No selection, use current line
            sel_start = text_area.index("insert linestart")
            sel_end = text_area.index("insert lineend")
        start_line = int(sel_start.split('.')[0])
        end_line = int(sel_end.split('.')[0])
        for line in range(start_line, end_line + 1):
            line_start = f"{line}.0"
            line_end = f"{line}.end"
            line_text = text_area.get(line_start, line_end)
            # Remove existing heading marks
            new_text = line_text.lstrip('# ').lstrip()
            if style == "Heading 1":
                new_text = "# " + new_text
            elif style == "Heading 2":
                new_text = "## " + new_text
            elif style == "Heading 3":
                new_text = "### " + new_text
            # else: Normal text, just remove heading
            text_area.delete(line_start, line_end)
            text_area.insert(line_start, new_text)
        self.update_preview()


    def apply_font(self, font_name):
        """
        Applies the selected font to the text area and updates the preview.

        :param string font_name: The name of the font to be applied.
        """

        # Change the font for all editors
        import tkinter.font
        # If font_name contains spaces and a style (e.g., 'Arial Light'), use only the first part as the family
        family = font_name.split()[0]
        size = self.font_size_var.get()
        font = tkinter.font.Font(family=family, size=size)
        for text_area in self.editors:
            text_area.configure(font=font)
        self.current_font_family = family
        self.update_preview()


    def change_font_size(self, delta):
        """
        Changes the font size by a given value (limited to a minimum of 6).

        :param int delta: The change in font size. 
        """
        
        new_size = max(6, self.font_size_var.get() + delta)
        self.font_size_var.set(new_size)
        self.apply_font(self.font_var.get())
        self.current_font_size = new_size
        self.update_preview()


    def _on_ctrl_scroll(self, event):
        """
        Zooms font size when Ctrl is held, otherwise allows normal scrolling.
        When zooming, returns "break" to prevent default scroll.
        When scrolling, doesn't return "break" to allow scrollbar updates.

        :param Event event: The MouseWheel event.

        :return: A str "break" only when zooming, None when scrolling normally.
        """

        if event.state & 0x4:
            if event.delta > 0:
                self.change_font_size(1)
            else:
                self.change_font_size(-1)
            return "break"
        # For normal scrolling, don't return "break" to allow default behavior


    def _on_linux_scroll(self, event):
        """
        Zooms font size on Ctrl+scroll for Linux (Button-4/5 events),
        otherwise allows normal scrolling.

        :param Event event: The button event (num 4 = up, 5 = down).

        :return: A str "break" only when zooming, None when scrolling normally.
        """

        if event.state & 0x4:
            if event.num == 4:
                self.change_font_size(1)
            else:
                self.change_font_size(-1)
            return "break"
        # For normal scrolling, don't return "break" to allow default behavior


    def _on_middle_press(self, event):
        """
        Records the starting Y position and font size for middle-click drag zoom.

        :param Event event: The middle mouse button press event.

        :return: None to allow default scroll behavior.
        """

        self._zoom_drag_y = event.y_root
        self._zoom_drag_base_size = self.font_size_var.get()
        self._zoom_activated = False


    def _on_middle_drag(self, event):
        """
        Zooms font size based on vertical mouse movement while middle button
        is held. Moving up zooms in, moving down zooms out (10px per step).
        Only activates zoom with significant movement (>15px).

        :param Event event: The mouse motion event.

        :return: A str "break" only when actively zooming.
        """

        if not hasattr(self, '_zoom_drag_y'):
            return
        delta_px = self._zoom_drag_y - event.y_root
        
        # Only activate zoom if movement is significant
        if abs(delta_px) > 15:
            self._zoom_activated = True
            new_size = max(6, self._zoom_drag_base_size + delta_px // 10)
            if new_size != self.font_size_var.get():
                self.font_size_var.set(new_size)
                self.apply_font(self.font_var.get())
                self.current_font_size = new_size
            return "break"


    def _on_middle_release(self, event):
        """
        Cleans up drag state and refreshes the preview after middle-click zoom.

        :param Event event: The middle mouse button release event.

        :return: None to allow default behavior.
        """

        if hasattr(self, '_zoom_drag_y'):
            if hasattr(self, '_zoom_activated') and self._zoom_activated:
                self.update_preview()
            del self._zoom_drag_y
            del self._zoom_drag_base_size
            if hasattr(self, '_zoom_activated'):
                del self._zoom_activated


    def toggle_bold(self):
        """
        Takes the existing text area and adds/removes the bold Markdown syntax to toggle boldness.
        """
        
        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # If already bold, remove **, else add **
            if selected_text.startswith("**") and selected_text.endswith("**") and len(selected_text) > 4:
                new_text = selected_text[2:-2]
            else:
                new_text = f"**{selected_text}**"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            dialogs.Messagebox.show_info("No selection", "Please select text to make bold.")
            return
        self.update_preview()


    def toggle_italic(self):
        """
        Takes the existing text area and adds/removes the italic Markdown syntax to toggle italicness.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # If already italic, remove *, else add * (single asterisk)
            if (selected_text.startswith("*") and selected_text.endswith("*") and len(selected_text) > 2) or \
               (selected_text.startswith("_") and selected_text.endswith("_") and len(selected_text) > 2):
                new_text = selected_text[1:-1]
            else:
                new_text = f"*{selected_text}*"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            dialogs.Messagebox.show_info("No selection", "Please select text to make italic.")
            return
        self.update_preview()


    def toggle_underline(self):
        """
        Takes the existing text area and adds/removes the underline Markdown syntax to toggle underline.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # Use HTML <u> for underline in Markdown (not standard, but works in many renderers)
            if selected_text.startswith("<u>") and selected_text.endswith("</u>") and len(selected_text) > 7:
                new_text = selected_text[3:-4]
            else:
                new_text = f"<u>{selected_text}</u>"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            dialogs.Messagebox.show_info("No selection", "Please select text to underline.")
            return
        self.update_preview()


    def choose_fg_color(self):
        """
        Prompts the user to select a foreground colour, then applies it to the preview.

        :raises tk.TclError: If there is no text selection to apply the color to, or if there is an error accessing the text area or its contents.
        """
        
        import re
        cd = dialogs.ColorChooserDialog()
        cd.show()
        result = cd.result
        if result:
            color_hex = result.hex if hasattr(result, 'hex') else result
            text_area = self.get_current_text_area()
            if text_area:
                try:
                    sel_start = text_area.index("sel.first")
                    sel_end = text_area.index("sel.last")
                    selected_text = text_area.get(sel_start, sel_end)

                    if selected_text.strip() == "" or "\n" in selected_text:
                        dialogs.Messagebox.show_info("Tip", "Please select single-line non-empty text to set color.")
                        return

                    cleaned_text = re.sub(
                        r'<span style="color:[^">]+?">(.*?)</span>', r'\1', selected_text, flags=re.DOTALL
                    )
                    new_text = f'<span style="color:{color_hex}">{cleaned_text}</span>'

                    text_area.delete(sel_start, sel_end)
                    text_area.insert(sel_start, new_text)

                    self.current_fg_color = color_hex
                    self.update_preview()
                except tk.TclError:
                    dialogs.Messagebox.show_info("No selection", "Please select text to color.")
            

    def choose_bg_color(self):
        """
        Prompts the user to select a background colour, then applies it to the preview.
        """ 

        cd = dialogs.ColorChooserDialog()
        cd.show()
        color = cd.result
        if color:
            color = color.hex
            text_area = self.get_current_text_area()
            if text_area:
                text_area.config(bg=color)
                self.current_bg_color = color
                self.update_preview()
            

    def update_preview(self):
        """
        Checks that a file is open, and that there is a loaded text area, then updates the preview file.
        """
        
        if not self.current_file_path:
            return
        text_area = self.get_current_text_area()
        if not text_area:
            return
        update_preview(self)


    def undo_action(self):
        """
        Checks if there is a loaded text area, and that changes have been made, then attempts to undo the most recent change.

        :raises tk.TclError: If there is an error performing the undo operation, such as if there are no actions to undo.
        """
        
        text_area = self.get_current_text_area()
        if text_area and text_area.edit_modified():
            try:
                text_area.edit_undo()
            except tk.TclError:
                pass


    def redo_action(self):
        """
        Checks if there is a loaded text area, then attempts to redo the most recently undone change.

        :raises tk.TclError: If there is an error performing the redo operation, such as if there are no actions to redo.
        """

        text_area = self.get_current_text_area()
        if text_area:
            try:
                text_area.edit_redo()
            except tk.TclError:
                pass

    def _prompt_translation_languages(self):
        """
        Prompts user for source and target languages for AI translation.

        :return: Tuple (source_language, target_language) or (None, None) when cancelled.
        """

        # Create custom dialog with comboboxes
        dialog = tk.Toplevel(self.root)
        dialog.title("AI Translation - Select Languages")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog on parent
        dialog.geometry("400x280")
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 200
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 140
        dialog.geometry(f"+{x}+{y}")
        
        result = {"source": None, "target": None, "confirmed": False}
        
        # Source language
        ttk.Label(dialog, text="Source Language:").pack(pady=(20, 5))
        source_combo = ttk.Combobox(dialog, values=self.translation_languages, state="readonly", width=30)
        if self.translation_source_language in self.translation_languages:
            source_combo.set(self.translation_source_language)
        else:
            source_combo.current(0)
        source_combo.pack(pady=5)
        
        # Target language
        ttk.Label(dialog, text="Target Language:").pack(pady=(10, 5))
        target_combo = ttk.Combobox(dialog, values=self.translation_languages, state="readonly", width=30)
        if self.translation_target_language in self.translation_languages:
            target_combo.set(self.translation_target_language)
        else:
            target_combo.current(1)
        target_combo.pack(pady=5)
        
        def on_ok():
            result["source"] = source_combo.get()
            result["target"] = target_combo.get()
            result["confirmed"] = True
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="OK", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter and Escape keys
        dialog.bind("<Return>", lambda e: on_ok())
        dialog.bind("<Escape>", lambda e: on_cancel())
        
        # Wait for dialog to close
        dialog.wait_window()
        
        if not result["confirmed"]:
            return None, None

        self.translation_source_language = result["source"].strip()
        self.translation_target_language = result["target"].strip()
        return self.translation_source_language, self.translation_target_language

    def _get_translation_scope(self, text_area, selected_only):
        """
        Determines translation range and text based on selected scope.

        :param ScrolledText text_area: Active text editor.
        :param bool selected_only: True for selected text, False for full document.

        :return: Tuple (start_idx, end_idx, source_text).
        """

        if selected_only:
            try:
                start_idx = text_area.index("sel.first")
                end_idx = text_area.index("sel.last")
            except tk.TclError:
                dialogs.Messagebox.show_info("No selection", "Please select text before translating.")
                return None, None, None
        else:
            start_idx = "1.0"
            end_idx = "end-1c"

        source_text = text_area.get(start_idx, end_idx)
        if not source_text.strip():
            dialogs.Messagebox.show_info("Empty content", "Nothing to translate in the chosen scope.")
            return None, None, None

        return start_idx, end_idx, source_text

    def _apply_translation_result(self, tab_index, text_area, start_idx, end_idx, translated_text, ambiguity_notes):
        """
        Applies translated content back to the editor and keeps undo/redo usable.
        """

        try:
            text_area.edit_separator()
            text_area.delete(start_idx, end_idx)
            text_area.insert(start_idx, translated_text)
            text_area.edit_separator()

            self.mark_tab_modified(tab_index)
            self.update_preview()

            if ambiguity_notes:
                note_text = "\n".join([f"- {note}" for note in ambiguity_notes])
                dialogs.Messagebox.show_info(
                    "Translation Notes",
                    "Translation completed with ambiguity notes:\n\n" + note_text,
                )
        except Exception as exc:
            dialogs.Messagebox.show_error("Translation Error", f"Failed to apply translation: {exc}")
        finally:
            self.root.config(cursor="")

    def translate_with_ai(self, selected_only=False):
        """
        Translates selected text or full document using AI while preserving Markdown formatting.

        :param bool selected_only: True to translate selection only, False for full document.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            dialogs.Messagebox.show_info("No document", "Please open or create a document first.")
            return

        source_lang, target_lang = self._prompt_translation_languages()
        if not source_lang or not target_lang:
            return

        if source_lang.strip().lower() == target_lang.strip().lower():
            dialogs.Messagebox.show_info("Language Selection", "Source and target language are the same.")
            return

        start_idx, end_idx, source_text = self._get_translation_scope(text_area, selected_only)
        if source_text is None:
            return

        tab_index = self.notebook.index(self.notebook.select())
        self.root.config(cursor="watch")

        def worker():
            try:
                translated_text, ambiguity_notes = translate_markdown_with_ai(
                    source_text,
                    source_lang,
                    target_lang,
                )
                if not translated_text.strip():
                    raise RuntimeError("AI returned empty translation.")

                self.root.after(
                    0,
                    lambda: self._apply_translation_result(
                        tab_index,
                        text_area,
                        start_idx,
                        end_idx,
                        translated_text,
                        ambiguity_notes,
                    ),
                )
            except Exception as exc:
                current_provider = (self.ai_provider_var.get() or os.getenv("AI_PROVIDER", "openrouter")).strip().lower()
                self.root.after(
                    0,
                    lambda: (
                        self.root.config(cursor=""),
                        dialogs.Messagebox.show_error(
                            "AI Translation Failed",
                            f"Provider: {current_provider}\n"
                            f"{exc}\n\n"
                            "Tip: Configure .env using .env.example (AI_PROVIDER and provider API keys).",
                        ),
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def set_ai_provider(self, provider_name):
        """
        Sets current AI provider for translation at runtime.

        :param string provider_name: one of openrouter/openai/anthropic
        """

        normalized = (provider_name or "").strip().lower()
        if normalized == "athropic":
            normalized = "anthropic"

        if normalized not in ("openrouter", "openai", "anthropic"):
            dialogs.Messagebox.show_error("Invalid Provider", f"Unsupported provider: {provider_name}")
            return

        self.ai_provider_var.set(normalized)
        os.environ["AI_PROVIDER"] = normalized
        dialogs.Messagebox.show_info("AI Provider", f"AI provider switched to: {normalized}")

    def toggle_pdf_mode(self):
        """
        Toggles between PyMuPDF and Docling PDF conversion modes.
        """
        self.use_docling_pdf = self.pdf_mode_var.get()

    def show_pdf_converter_info(self):
        """
        Shows information about available PDF converters.
        """
        info_text = (
            "PDF Converter Information:\n\n"
            "1. PyMuPDF (Default)\n"
            "   - Speed: Very Fast\n"
            "   - Memory: Low\n"
            "   - Quality: Good for simple documents\n"
            "   - Best for: Text extraction, simple PDFs\n\n"
            "2. Docling (Advanced)\n"
            "   - Speed: Moderate (requires ML models)\n"
            "   - Memory: Higher\n"
            "   - Quality: Excellent for complex documents\n"
            "   - Best for: Academic papers, reports with tables\n"
            "   - Note: First use may take 2-5 seconds\n"
            "   - Install: pip install docling\n\n"
            "Current Mode: {}\n\n"
            "You can switch in Tools > Use Advanced PDF Conversion (Docling)"
        ).format("Docling (Advanced)" if self.use_docling_pdf else "PyMuPDF (Fast)")
        
        messagebox.showinfo("PDF Converter Information", info_text)

    def insert_table(self):
        """
        Inserts a table with customizable cell content at cursor position.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return
    
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Insert Table")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configuration frame at top
        config_frame = tk.Frame(dialog, relief=tk.RAISED, borderwidth=1)
        config_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        tk.Label(config_frame, text="Rows (including header):", anchor="w").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        rows_var = tk.IntVar(value=3)
        rows_spinbox = tk.Spinbox(config_frame, from_=2, to=20, textvariable=rows_var, width=10)
        rows_spinbox.grid(row=0, column=1, padx=5, pady=5)
    
        tk.Label(config_frame, text="Columns:", anchor="w").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        cols_var = tk.IntVar(value=3)
        cols_spinbox = tk.Spinbox(config_frame, from_=2, to=10, textvariable=cols_var, width=10)
        cols_spinbox.grid(row=0, column=3, padx=5, pady=5)
        
        # Canvas frame for table grid
        canvas_frame = tk.Frame(dialog)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        canvas = tk.Canvas(canvas_frame, borderwidth=0)
        scrollbar_v = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollbar_h = tk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_v.pack(side="right", fill="y")
        scrollbar_h.pack(side="bottom", fill="x")
        
        # Store cell entries
        cell_entries = []
        
        def create_table_grid():
            """
            Creates or recreates the table grid based on current dimensions.
            """
            
            # Clear existing entries
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            cell_entries.clear()
            
            rows = rows_var.get()
            cols = cols_var.get()
            
            # Create grid of entry widgets
            for r in range(rows):
                row_entries = []
                for c in range(cols):
                    # Determine default content
                    if r == 0:
                        default_text = f"Header {c+1}"
                    else:
                        default_text = f"Cell {r}-{c+1}"
                    
                    # Create entry with label
                    cell_frame = tk.Frame(scrollable_frame, relief=tk.RIDGE, borderwidth=1)
                    cell_frame.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                    
                    label = tk.Label(cell_frame, text=f"[{r},{c}]", font=("Arial", 8), fg="gray")
                    label.pack(anchor="nw", padx=2, pady=2)
                    
                    entry = tk.Entry(cell_frame, width=15)
                    entry.insert(0, default_text)
                    entry.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
                    
                    row_entries.append(entry)
                
                cell_entries.append(row_entries)
            
            # Make columns expandable
            for c in range(cols):
                scrollable_frame.columnconfigure(c, weight=1)
        
        def update_table_grid(*args):
            """
            Updates the table grid when dimensions change.
            """
            
            create_table_grid()
        
        # Bind spinbox changes to update grid
        rows_var.trace_add("write", update_table_grid)
        cols_var.trace_add("write", update_table_grid)
        
        # Initial table grid
        create_table_grid()
        
        def insert_table_content():
            """
            Generates table markdown from entry widgets and updates the preview file.
            """

            rows = rows_var.get()
            cols = cols_var.get()
            table_lines = []
            
            # Header row
            header_values = [entry.get().strip() or f"Header {i+1}" for i, entry in enumerate(cell_entries[0])]
            header = "| " + " | ".join(header_values) + " |"
            table_lines.append(header)
            
            # Separator row
            separator = "| " + " | ".join(["---" for _ in range(cols)]) + " |"
            table_lines.append(separator)
            
            # Data rows
            for row_idx in range(1, rows):
                row_values = [entry.get().strip() or f"Cell {row_idx}-{i+1}" for i, entry in enumerate(cell_entries[row_idx])]
                data_row = "| " + " | ".join(row_values) + " |"
                table_lines.append(data_row)
            
            table_text = "\n" + "\n".join(table_lines) + "\n\n"
            
            # Insert at cursor position
            text_area.insert("insert", table_text)
            dialog.destroy()
            self.update_preview()
        
        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(side=tk.BOTTOM, pady=10)
        
        tk.Button(button_frame, text="Insert Table", command=insert_table_content, width=15, height=1, bg="#4CAF50", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy, width=15, height=1).pack(side=tk.LEFT, padx=5)
        
        # Set dialog size based on initial table dimensions
        width = min(800, 180 * cols_var.get() + 120)
        height = min(650, 80 * rows_var.get() + 200)
        dialog.geometry(f"{width}x{height}")
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        dialog.wait_window()

    def show_table_help(self):
        """
        Shows the help dialog for table syntax.
        """
        
        help_text = """📋 Markdown Table Syntax Guide

Basic Table Structure:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |

Column Alignment:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Left Align | Center Align | Right Align |
|:-----------|:------------:|------------:|
| Left       | Center       | Right       |
| Text       | Text         | Text        |

Alignment Syntax:
  • Left:    |:---|     (colon on left)
  • Center:  |:--:|     (colon on both sides)
  • Right:   |---:|     (colon on right)

Quick Tips:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Use | to separate columns
✓ Second row must be separator (- - -)
✓ Separators need at least 3 dashes
✓ Outer pipes | are optional but recommended
✓ Cell content width doesn't need to match
✓ Use Table menu → Insert Table for quick creation

Example - Data Table:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Name    | Age | Country |
|:--------|:---:|--------:|
| Alice   | 25  | USA     |
| Bob     | 30  | Canada  |
| Charlie | 28  | UK      |
"""
        messagebox.showinfo("Markdown Table Syntax Help", help_text)

    def export_to_html_dialog(self):
        """
        Shows dialog to export current the markdown document to HTML.
        """
        
        if not self.editors:
            dialogs.Messagebox.show_info("Info", "No document to export.")
            return
        
        # Get current file path to suggest HTML filename
        idx = self.notebook.index(self.notebook.select())
        current_path = self.file_paths[idx]
        
        # Suggest filename
        if current_path:
            base_name = os.path.splitext(os.path.basename(current_path))[0]
            initial_dir = os.path.dirname(current_path)
            initial_file = f"{base_name}.html"
        else:
            initial_dir = os.path.expanduser("~")
            initial_file = "document.html"
        
        # Show save dialog
        output_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
            title="Export to HTML"
        )
        
        if output_path:
            export_to_html(self, output_path)


    def export_to_docx_dialog(self):
        """
        Shows the dialog to export the current markdown document to Word.
        """
        
        if not self.editors:
            dialogs.Messagebox.show_info("Info", "No document to export.")
            return
        
        # Get current file path to suggest Word filename
        idx = self.notebook.index(self.notebook.select())
        current_path = self.file_paths[idx]
        
        # Suggest filename
        if current_path:
            base_name = os.path.splitext(os.path.basename(current_path))[0]
            initial_dir = os.path.dirname(current_path)
            initial_file = f"{base_name}.docx"
        else:
            initial_dir = os.path.expanduser("~")
            initial_file = "document.docx"
        
        # Show save dialog
        output_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
            title="Export to Word"
        )
        
        if output_path:
            export_to_docx(self, output_path)


    def export_to_pdf_dialog(self):
        """
        Shows the dialog to export the current markdown document to PDF.
        """
        
        if not self.editors:
            dialogs.Messagebox.show_info("Info", "No document to export.")
            return
        
        # Get current file path to suggest PDF filename
        idx = self.notebook.index(self.notebook.select())
        current_path = self.file_paths[idx]
        
        # Suggest filename
        if current_path:
            base_name = os.path.splitext(os.path.basename(current_path))[0]
            initial_dir = os.path.dirname(current_path)
            initial_file = f"{base_name}.pdf"
        else:
            initial_dir = os.path.expanduser("~")
            initial_file = "document.pdf"
        
        # Show save dialog
        output_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF documents", "*.pdf"), ("All files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
            title="Export to PDF"
        )
        
        if not output_path:
            return

        # Take the content markdown now
        md_content = self.editors[idx].get("1.0", "end-1c")

        # Convert to HTML (preserve fenced code blocks and common markdown features)
        html_content = markdown.markdown(
            md_content,
            extensions=["fenced_code", "tables", "nl2br", "sane_lists"]
        )

        # Determine base URL for resolving relative image paths
        base_url = None
        if current_path:
            base_url = os.path.dirname(os.path.abspath(current_path))

        # Export to PDF using WeasyPrint
        export_markdown_to_pdf(html_content, output_path, base_url)
