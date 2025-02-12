# -*- coding: utf-8 -*-
# ---------------------------
# 配置与常量定义
import sys
sys.stdout.reconfigure(encoding='utf-8')

from kivy.config import Config
from kivy.animation import Animation
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.gridlayout import GridLayout
from defines import *
import datetime
import json
import os


from data import Event, Routine
from utils import log, hex_to_rgba, rgb_to_hex, get_fitted_text, log_position, get_absolute_pos

log("DEBUG 模式已开启", "green")
Config.set('graphics', 'fullscreen', '0')
Config.set('graphics', 'width', str(WINDOW_WIDTH))
Config.set('graphics', 'height', str(WINDOW_HEIGHT))
log(f"window size set | width: {WINDOW_WIDTH}, height: {WINDOW_HEIGHT}", "green")

from kivy.core.text import LabelBase
from kivy.core.text import Label as CoreLabel

LabelBase.register(name='KingHwa_OldSong', fn_regular='resources/KingHwa_OldSong.ttf')
LabelBase.register(name='wqy_zenhei', fn_regular='resources/wqy-zenhei.ttc')

# ---------------------------
# 导入 Kivy 模块
from kivy.uix.widget import Widget
from kivy.graphics import Line, InstructionGroup
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.colorpicker import ColorPicker
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.core.image import Image as CoreImage
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.properties import ListProperty
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock


from kivy.uix.anchorlayout import AnchorLayout
from kivy.properties import ListProperty
from kivy.graphics import Color, Rectangle
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from defines import STAMP_BUTTON_SIZE  # 新定义的尺寸常量

class StampButton(ButtonBehavior, AnchorLayout):
    # 定义背景颜色属性，初始为全白
    background_color = ListProperty([1, 1, 1, 1])

    def __init__(self, stamp_name, texture, **kwargs):
        super(StampButton, self).__init__(**kwargs)
        self.stamp_name = stamp_name
        self.texture_obj = texture

        # 设置按钮为固定尺寸（正方形）
        self.size_hint = (None, None)
        self.size = (STAMP_BUTTON_SIZE, STAMP_BUTTON_SIZE)

        # 在 canvas.before 中绘制背景矩形
        with self.canvas.before:
            self.bg_color = Color(*self.background_color)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg, background_color=self.update_bg_color)

        # 计算印章图片尺寸为按钮 90%（居中显示）
        stamp_img_size = (self.size[0] * 0.9, self.size[1] * 0.9)
        self.stamp_img = Image(texture=texture,
                               size_hint=(None, None),
                               size=stamp_img_size,
                               allow_stretch=True,
                               keep_ratio=True)
        # 将印章图片添加到 AnchorLayout 中（默认居中）
        self.add_widget(self.stamp_img)

    def update_bg(self, *args):
        # 更新背景矩形的位置和尺寸
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def update_bg_color(self, *args):
        # 当 background_color 改变时更新背景颜色
        self.bg_color.rgba = self.background_color



# ---------------------------
# TimelineWidget：卷轴绘制区域
class TimelineWidget(Widget):
    """
    功能：单击创建事件（以半小时为基本单元，不再支持长按拖动）
    新功能：
      - 事件关系管理（采用字典存储，id 作为 key）
      - 增加盖章参数：stamped（是否盖章）、stamp_name（印章名称）、stamp_type（"full" 或 "half"）
      - 增加印章模式（stamp_mode_active 和 selected_stamp）用于功能区印章操作
    """

    def __init__(self, **kwargs):
        super(TimelineWidget, self).__init__(**kwargs)
        self.events = {}
        self.routines = {}
        self.recent_colors = []

        self.current_week_offset = 0
        self.max_event_id = 1
        self._touch_half_index = None

        self.static_layer = InstructionGroup()
        self.routine_layer = InstructionGroup()
        self.top_scale_layer = InstructionGroup()
        self.event_layer = InstructionGroup()

        self.canvas.add(self.static_layer)
        self.canvas.add(self.routine_layer)
        self.canvas.add(self.top_scale_layer)
        self.canvas.add(self.event_layer)

        # 加载印章图片，从 stamps 文件夹读取 png 文件
        self.stamp_images = {}
        stamp_folder = "stamps"
        if os.path.exists(stamp_folder):
            for file in sorted(os.listdir(stamp_folder)):
                if file.lower().endswith(".png"):
                    full_path = os.path.join(stamp_folder, file)
                    try:
                        file_key = file.replace('.png', '').split(".")[1]
                        img = CoreImage(full_path)
                        self.stamp_images[file_key] = img.texture
                    except Exception as e:
                        print("加载印章出错", file, e)
        else:
            if DEBUG:
                print("stamps 文件夹不存在")

        # 加载半小时印章，从 half_stamps 文件夹读取 png 文件
        self.half_stamp_images = {}
        half_stamp_folder = "half_stamps"
        if os.path.exists(half_stamp_folder):
            for file in os.listdir(half_stamp_folder):
                if file.lower().endswith(".png"):
                    full_path = os.path.join(half_stamp_folder, file)
                    try:
                        img = CoreImage(full_path)
                        self.half_stamp_images[file] = img.texture
                    except Exception as e:
                        print("加载半小时印章出错", file, e)
        else:
            if DEBUG:
                print("half_stamps 文件夹不存在")

        self.load_recent_colors()
        self.load_week_files("event")
        self.load_week_files("routine")

        # 印章模式相关属性（功能区使用）
        self.stamp_mode_active = False
        self.selected_stamp = list(self.stamp_images.keys())[0] if self.stamp_images else None
        self.selected_half_stamp = list(self.half_stamp_images.keys())[0] if self.half_stamp_images else None

        self.bind(size=self._update_layers, pos=self._update_layers)
        self._update_layers(update_static=True, update_routine=True, update_top_scale=True, update_event=True)
        Clock.schedule_once(lambda dt: self.center_on_current_hour(), 0)

        log("TimelineWidget 初始化完成", "green")

    # File operations
    def get_current_week_monday(self):
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        monday += datetime.timedelta(weeks=self.current_week_offset)
        return monday

    def get_week_filename(self, content="event"):
        assert content in ("event", "routine")
        monday = self.get_current_week_monday()
        sunday = monday + datetime.timedelta(days=6)
        filename = f"saves/{content}_{monday.strftime('%Y%m%d')}-{sunday.strftime('%Y%m%d')}.json"
        log(f"get_week_filename: {filename} (current_week_offset={self.current_week_offset})", "yellow")
        return filename

    def save_week_files(self, content="event"):
        assert content in ("event", "routine")
        filename = self.get_week_filename(content)
        tar = {"routine": self.routines, "event": self.events}[content]
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in tar.items()}, f, ensure_ascii=False, indent=2)
            log(f"Save to {filename} successfully", "yellow")
        except Exception as e:
            log(f"Save to {filename} failed: {e}", "red")

    def load_week_files(self, content="event"):
        assert content in ("event", "routine")
        filename = self.get_week_filename(content)
        tar_cls = {"event": Event, "routine": Routine}[content]
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if content == "event":
                        self.events = {int(k): tar_cls.from_dict(v) for k, v in data.items()}
                    elif content == "routine":
                        self.routines = {int(k): tar_cls.from_dict(v) for k, v in data.items()}

                log(f"Load from {filename} successfully", "yellow")
            except Exception as e:
                log(f"Load from {filename} failed: {e}", "red")
        for event in self.events.values():
            event.assign_events_dict(self.events)
            event.assign_child_and_parent()
        for routine in self.routines.values():
            routine.assign_routines_dict(self.routines)
        print(self.events)

    def save_recent_colors(self):
        try:
            with open("saves/recent_colors.json", 'w', encoding='utf-8') as f:
                json.dump(self.recent_colors, f, ensure_ascii=False, indent=2)
            log("Save recent colors successfully", "yellow")
        except Exception as e:
            log(f"Save recent colors failed: {e}", "red")

    def load_recent_colors(self):
        if os.path.exists("saves/recent_colors.json"):
            try:
                with open("saves/recent_colors.json", 'r', encoding='utf-8') as f:
                    self.recent_colors = json.load(f)
                log("Load recent colors successfully", "yellow")
            except Exception as e:
                log(f"Load recent colors failed: {e}", "red")

    # Utils functions
    @staticmethod
    def get_contrasting_text_color(background_color):
        # background_color 是一个 (R, G, B, A) 元组，假设 R,G,B 范围在 0～1
        r, g, b, _ = background_color
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        # 根据 brightness 的值选择文本颜色
        if brightness < 0.5:
            # 背景较暗，返回白色
            return (1, 1, 1, 1)
        else:
            # 背景较亮，返回黑色
            return (0, 0, 0, 1)


    def get_time_string(self, event_id):
        """
        根据 event_id 返回该时刻的时间字符串。
        这里 event_id 表示从本周一 0 点开始经过的半小时数，
        如 event_id 为 0 表示周一 0:00，
        event_id 为 1 表示周一 0:30，
        event_id 为 2 表示周一 1:00，依此类推。

        返回格式：
            如果分钟为 00，则返回 "MM月DD日 星期X HH点"
            如果分钟不为 00，则返回 "MM月DD日 星期X HH点MM分"
        """
        # 获取本周一的日期（datetime.date）
        monday = self.get_current_week_monday()
        # 将本周一日期转换为 datetime（当天 0:00）
        monday_datetime = datetime.datetime.combine(monday, datetime.time(0, 0))
        # 根据 event_id 计算时刻，假设 event_id 表示半小时数，所以每个 event_id 对应 30 分钟
        event_time = monday_datetime + datetime.timedelta(minutes=event_id * 30)

        # 定义星期的显示名称，datetime.weekday() 返回 0～6，其中 0 表示星期一
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

        # 根据分钟是否为 00 来构造不同的时间字符串
        if event_time.minute == 0:
            time_str = f"始于 {event_time.month}月{event_time.day}日 " + weekdays[
                event_time.weekday()] + event_time.strftime(" %H点")

        else:
            time_str = f"始于 {event_time.month}月{event_time.day}日 " + weekdays[
                event_time.weekday()] + event_time.strftime(" %H点30分")

        return time_str

    def is_cell_occupied(self, cell_index):
        event_cur: Event = self.events.get(cell_index, None)
        if event_cur:  # current cell has event
            return event_cur.id
        event_prev: Event = self.events.get(cell_index - 1, None)
        if event_prev and not event_prev.is_half:  # previous cell has full event that occupies current cell
            return event_prev.id
        return False

    def is_cell_and_next_occupied(self, cell_index):
        event_cur: Event = self.events.get(cell_index, None)
        if event_cur:  # current cell has event
            return event_cur.id
        event_prev: Event = self.events.get(cell_index - 1, None)
        if event_prev and not event_prev.is_half:  # previous cell has full event that occupies current cell
            return event_prev.id
        event_next: Event = self.events.get(cell_index + 1, None)
        if event_next:  # next cell has event
            return event_next.id
        return False

    def get_cell_event(self, cell_index):
        if self.events.get(cell_index, None):  # current cell has event
            return self.events[cell_index]
        elif self.events.get(cell_index - 1, None):  # previous cell has full event that occupies current cell
            if not self.events[cell_index - 1].is_half:
                return self.events[cell_index - 1]
        return None

    def get_cell_routine(self, cell_index):
        return self.routines.get(cell_index, None)  # routine occupies 1 cell only

    def get_previous_event(self, event: Event = None, event_id=None):
        assert (event or event_id) and not (event and event_id)
        event_start_col = event_id if event_id else event.id
        if event_start_col - 1 in self.events:
            prev_event = self.events[event_start_col - 1]
            if prev_event.is_half:
                return prev_event
        elif event_start_col - 2 in self.events:
            prev_event = self.events[event_start_col - 2]
            if not prev_event.is_half:
                return prev_event
        return None

    def add_recent_color(self, color_hex):
        if color_hex in self.recent_colors:
            self.recent_colors.remove(color_hex)
        self.recent_colors.insert(0, color_hex)
        if len(self.recent_colors) > 10:
            self.recent_colors.pop()
        self.save_recent_colors()  # 每次更新后保存到本地文件


    def get_color_picker_widget(self, initial_color=None):
        container = BoxLayout(orientation='vertical', spacing=10)
        cp = ColorPicker(size_hint_y=None, height=300)
        if initial_color:
            cp.color = initial_color
        hex_input = TextInput(
            text=rgb_to_hex(cp.color),
            multiline=False,
            size_hint_y=None,
            height=40,
            font_name=COLOR_INPUT_FONT,
            hint_text="输入Hex代码后回车确认"
        )

        def on_hex_validate(instance):
            hex_str = instance.text.strip()
            if len(hex_str) == 7 and hex_str.startswith('#'):
                try:
                    new_color = hex_to_rgba(hex_str)
                    cp.color = new_color
                    instance.text = rgb_to_hex(cp.color)
                    self.add_recent_color(instance.name)
                    update_recent_grid()
                except Exception as e:
                    pass

        hex_input.bind(on_text_validate=on_hex_validate)
        container.add_widget(cp)
        container.add_widget(hex_input)
        recent_colors_area = GridLayout(cols=5, size_hint_y=None, height=100, spacing=5)
        container.add_widget(recent_colors_area)

        def update_recent_grid():
            recent_colors_area.clear_widgets()
            for color_hex in self.recent_colors:
                btn = Button(text="", background_normal="", background_color=hex_to_rgba(color_hex))

                def on_recent_color(instance, color=color_hex):
                    cp.color = hex_to_rgba(color)
                    hex_input.text = rgb_to_hex(cp.color)
                    self.add_recent_color(hex_input.text)
                    update_recent_grid()

                btn.bind(on_release=on_recent_color)
                recent_colors_area.add_widget(btn)

        update_recent_grid()
        cp.bind(color=lambda instance, value: hex_input.setter('text')(hex_input, rgb_to_hex(value)))
        return container, cp, hex_input

    def center_on_current_hour(self):
        now = datetime.datetime.now()
        monday = self.get_current_week_monday()
        hour_offset = int((now - datetime.datetime.combine(monday, datetime.time.min)).total_seconds() // 3600)
        scrollview = self.parent
        desired_x = hour_offset * HOUR_WIDTH - (scrollview.width / 2) + (HOUR_WIDTH / 2)
        desired_x = max(0, min(desired_x, TIMELINE_WIDTH - scrollview.width))
        if TIMELINE_WIDTH - scrollview.width > 0:
            scrollview.scroll_x = desired_x / (TIMELINE_WIDTH - scrollview.width)
        else:
            scrollview.scroll_x = 0

    def slide_to_current_hour(self):
        import datetime
        now = datetime.datetime.now()
        monday = self.get_current_week_monday()
        hour_offset = int((now - datetime.datetime.combine(monday, datetime.time.min)).total_seconds() // 3600)
        scrollview = self.parent  # 前提是 TimelineWidget 已经放在 ScrollView 内
        desired_x = hour_offset * HOUR_WIDTH - (scrollview.width / 2) + (HOUR_WIDTH / 2)
        desired_x = max(0, min(desired_x, TIMELINE_WIDTH - scrollview.width))
        if TIMELINE_WIDTH - scrollview.width > 0:
            target_scroll = desired_x / (TIMELINE_WIDTH - scrollview.width)
        else:
            target_scroll = 0

        # 使用动画平滑滚动到目标位置
        anim = Animation(scroll_x=target_scroll, duration=1.5, t='out_quad')
        anim.start(scrollview)

    @staticmethod
    def calculate_time_placeholders(col_half_hour, is_half):
        if col_half_hour is None:
            return None
        col = col_half_hour // 2
        start_at_30_minute = col_half_hour % 2
        if start_at_30_minute:
            if is_half:
                time_placeholder = f"{col:02d}:30 - {col + 1:02d}:00"
            else:
                time_placeholder = f"{col:02d}:30 - {col + 1:02d}:30"
        else:
            if is_half:
                time_placeholder = f"{col:02d}:00 - {col + 1:02d}:30"
            else:
                time_placeholder = f"{col:02d}:00 - {col + 1:02d}:00"
        return time_placeholder

    # Event logical operations

    def _create_new_routine(self, routine_id, text, color, text_color, border_color, border_thickness, line_height):
        new_routine = Routine(routine_id=routine_id,
                              name=text, color=color,
                              text_color=text_color,
                              border_color=border_color,
                              border_thickness=border_thickness,
                              line_height=line_height,
                              routines_dict=self.routines)
        self.routines[routine_id] = new_routine
        return new_routine

    @staticmethod
    def _modify_routine(routine: Routine, text, color, text_color, border_color, border_thickness, line_height):
        routine.name = text
        routine.color = color
        routine.text_color = text_color
        routine.border_color = border_color
        routine.border_thickness = border_thickness
        routine.line_height = line_height
        return routine

    def _create_new_event(self, event_id, name, color, text_color, border_color,
                          is_half, is_child, is_parent, popup):
        # only `is_half_final` is passed to Event constructor
        # as `is_child_of_prev_final` and `is_parent_of_next_final` are used to determine parent/child relationship
        # and may change during the process
        new_event = Event(event_id=event_id,
                          name=name,
                          color=color,
                          text_color=text_color,
                          border_color=border_color,
                          is_half=is_half,
                          border_thickness=EVENT_BORDER_THICKNESS,
                          events_dict=self.events)
        log(f"创建新事件: event_id:{event_id}, name: {name}, is_half: {is_half},     ", "blue")
        if is_child:
            prev_event: Event = self.get_previous_event(new_event)
            if prev_event is None:  # no previous event, undo child status
                new_event.is_child = False  # this is not necessary, but for clarity
            elif new_event.is_half and prev_event.is_half:  # both half, make previous full, remove new (return None)
                prev_event.become_full()
                return None
            elif new_event.is_half and not prev_event.is_half:  # half and full, set parent
                new_event.add_parent(parent=prev_event, half_stamp_name=self.selected_half_stamp)
            else:  # full and half or both full, should not happen
                raise ValueError("不应该出现的情况")

        self.events[event_id] = new_event

        if is_parent:  # create next half event and set child
            ext_event = Event(event_id=event_id + 2,
                              name=name,
                              is_half=True,
                              color=color,
                              text_color=text_color,
                              border_color=EVENT_BORDER_COLOR,
                              border_thickness=EVENT_BORDER_THICKNESS,
                              events_dict=self.events)
            new_event.add_child(child=ext_event, half_stamp_name=self.selected_half_stamp)
            self.events[event_id + 2] = ext_event

        return new_event

    def week_repeat(self, event: Event = None, routine: Routine = None):
        assert (event or routine) and not (event and routine)
        origin_id = event.id if event else routine.id
        base_id = origin_id % 48
        if event and event.is_half:
            for possible_id in range(base_id, 335, 48):
                if self.is_cell_occupied(possible_id):
                    continue
                else:
                    event.copy_event(new_event_id=possible_id)
        elif event and not event.is_half:
            for possible_id in range(base_id, 335, 48):
                if self.is_cell_and_next_occupied(possible_id):
                    continue
                else:
                    event.copy_event(new_event_id=possible_id)
        else:
            for possible_id in range(base_id, 335, 48):
                if self.is_cell_occupied(possible_id):
                    continue
                else:
                    routine.copy_routine(new_routine_id=possible_id)

    def clear_week_repeat(self, event: Event = None, routine: Routine = None):
        assert (event or routine) and not (event and routine)
        origin_id = event.id if event else routine.id
        base_id = origin_id % 48
        for possible_id in range(base_id, 335, 48):
            if possible_id != origin_id and event:
                event.clear_copy(tar_id=possible_id)
            elif possible_id != origin_id and routine:
                routine.clear_copy(tar_id=possible_id)

    def _modify_event(self, event: Event, name, color, text_color, border_color,
                      is_half, is_child, is_parent, popup):
        """修改事件逻辑；盖章参数在 on_confirm 中单独处理"""
        event.name = name
        event.color = color
        event.text_color = text_color
        event.border_color = border_color
        event.become_half() if is_half else event.become_full()  # half -> full or full -> half if needed

        if is_child:
            if event.is_child:  # already child, no change
                pass
            else:  # find previous event and set parent
                prev_event: Event = self.get_previous_event(event)
                if prev_event is None:
                    event.is_child = False
                elif event.is_half and prev_event.is_half:
                    prev_event.become_full()
                    self.events.pop(event.id)
                    return None
                elif event.is_half and not prev_event.is_half:
                    event.add_parent(parent=prev_event, half_stamp_name=self.selected_half_stamp)
                else:
                    raise ValueError("不应该出现的情况")
        else:  # remove parent if exists
            event.remove_parent()

        if is_parent:
            log(f"设置为父事件: {event.id}", "red")
            if event.is_parent:  # already parent, no change
                pass
            else:  # create next half event and set child; event is full so next event has id + 2
                ext_event = Event(event_id=event.id + 2,
                                  name=name,
                                  is_half=True,
                                  color=color,
                                  text_color=text_color,
                                  border_color=EVENT_BORDER_COLOR,
                                  border_thickness=EVENT_BORDER_THICKNESS,
                                  events_dict=self.events)
                event.add_child(child=ext_event, half_stamp_name=self.selected_half_stamp)
                self.events[event.id + 2] = ext_event
        else:  # remove child if exists
            log(f"取消为父事件: {event.id}, {event.is_parent}", "red")
            event.remove_child()
        return event

    # Layer operations
    def _update_layers(self, update_static=False, update_routine=False, update_top_scale=False, update_event=False,
                       save_routine=False, save_event=False):
        if update_static:
            log("update_static", "purple")
            self._update_static_layer()
        if update_routine:
            log("update_routine", "purple")
            self._update_routine_layer(save_file=save_routine)
        if update_top_scale:
            log("update_top_scale", "purple")
            self._update_scale_layer()
        if update_event:
            log("update_event", "purple")
            self._update_event_layer(save_file=save_event)

    # event_layer: all event in drawing region
    def _update_event_layer(self, save_file=True):
        self.event_layer.clear()
        for event in self.events.values():
            self._draw_event(event)
        if save_file:
            self.save_week_files("event")

        self._draw_poster()



    def _update_scale_layer(self):
        self.top_scale_layer.clear()
        self._update_top_scale_layer()
        self._update_bottom_scale_layer()

    # top_scale_layer: all top scale in top scale region
    def _update_top_scale_layer(self):
        top_scale_region_bottom = self.y + BOTTOM_SCALE_AREA_HEIGHT + DRAWING_AREA_HEIGHT
        day_width = TIMELINE_WIDTH / 7.0
        for day in range(7):
            day_start_x = self.x + day * day_width
            for i, interval in enumerate(TOPIC_SCALE_INTERVALS):
                start_hr, end_hr = interval
                interval_x = day_start_x + (start_hr / 24.0) * day_width
                interval_width = ((end_hr - start_hr) / 24.0) * day_width
                interval_y = UPPER_SCALE_Y
                interval_height = SCALE_HEIGHT
                self.top_scale_layer.add(Color(*hex_to_rgba(TOP_SCALE_COLOR_INTERVAL_FILL[i])))
                self.top_scale_layer.add(
                    Rectangle(pos=(interval_x, interval_y), size=(interval_width, interval_height)))
                self.top_scale_layer.add(Color(*hex_to_rgba(TOP_SCALE_INTERVAL_BORDER_COLOR[i])))
                self.top_scale_layer.add(Line(rectangle=(interval_x, interval_y, interval_width, interval_height),
                                              width=SCALE_BORDER_THICKNESS))
                text = TOP_SCALE_TEXTS[i]
                core_label = CoreLabel(text=text, font_size=SCALE_FONT_SIZE, font_name=SCALE_FONT,
                                       color=hex_to_rgba(TOP_COLOR_INTERVAL_TEXT_COLOR[i]))
                core_label.refresh()
                texture = core_label.texture
                text_padding = 5
                text_x = interval_x + text_padding
                text_y = interval_y + (interval_height - texture.height) / 2
                self.top_scale_layer.add(Color(1, 1, 1, 1))
                self.top_scale_layer.add(Rectangle(texture=texture, pos=(text_x, text_y), size=texture.size))

    # top_scale_layer: all top scale in top scale region
    def _update_bottom_scale_layer(self):

        y_offset = LOWER_SCALE_Y

        label_list = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        label_color = ["#FFFFFF", "#FFFFFF", "#FFFFFF", "#000000", "#000000", "#000000", "#000000", "#000000",
                       "#000000", "#000000", "#000000", "#FFFFFF", ]
        interval_color = ["#1A237E", "#311B92", "#37474F", "#FFF3E0", "#4CAF50", "#FFD600", "#D32F2F", "#8D6E63",
                          "#FF9800", "#EF6C00", "#6A1B9A", "#4527A0", ]
        interval_color = [
            "#393939",  # 1:00 - 夜里（纯灰）
            "#252525",  # 3:00 - 夜里（纯灰）
            "#766C3F",  # 5:00 - 从夜到上午的过渡色
            "#F5DB6B",  # 7:00 - 上午（纯浅黄）
            "#F2C77B",  # 9:00 - 上午过渡色（介于纯浅黄与稍偏橙之间）
            "#EEB38A",  # 11:00 - 由上午向下午过渡
            "#EB9F9A",  # 13:00 - 下午（纯浅红）
            "#ECA78A",  # 15:00 - 下午过渡色
            "#EDAF7A",  # 17:00 - 由下午向晚上过渡
            "#EEB76A",  # 19:00 - 晚上（纯浅橙）
            "#EEB76A",  # 21:00 - 晚上（纯浅橙）
            "#715F45"  # 23:00 - 从晚上向夜里过渡
        ]

        interval_width = HOUR_WIDTH * 2
        offset = -1  # we start at "丑時" which is 1:00 - 3:00;

        for start_hr in range(-1, 168, 2):
            list_index = (start_hr - offset) % 24 // 2
            interval_x = self.x + start_hr * HOUR_WIDTH
            interval_y = y_offset
            interval_height = SCALE_HEIGHT
            color = hex_to_rgba(interval_color[list_index])
            # color = (color[0], color[1], color[2], 0.7)
            self.top_scale_layer.add(Color(*color))
            self.top_scale_layer.add(
                Rectangle(pos=(interval_x, interval_y), size=(interval_width, interval_height)))
            self.top_scale_layer.add(Color(*hex_to_rgba("#FFFFFF")))
            self.top_scale_layer.add(Line(rectangle=(interval_x, interval_y, interval_width, interval_height),
                                          width=SCALE_BORDER_THICKNESS))
            text = label_list[list_index]
            core_label = CoreLabel(text=text, font_size=SCALE_FONT_SIZE, font_name=SCALE_FONT,
                                   color=hex_to_rgba(label_color[list_index]))
            core_label.refresh()
            texture = core_label.texture
            text_padding = 5
            # text_x = interval_x + text_padding
            text_x = interval_x + (interval_width - texture.width) / 2
            text_y = interval_y + (interval_height - texture.height) / 2
            self.top_scale_layer.add(Color(1, 1, 1, 1))
            self.top_scale_layer.add(Rectangle(texture=texture, pos=(text_x, text_y), size=texture.size))

        mask_y = y_offset - 15
        mask_height = SCALE_HEIGHT + 30
        # 左侧遮罩：覆盖左边多出的部分（例如，从 X = self.x + (-1)*HOUR_WIDTH 到 self.x）
        left_mask_x = self.x + (-1) * HOUR_WIDTH - 20
        left_mask_width = HOUR_WIDTH + 21  # 覆盖1小时宽度
        self.top_scale_layer.add(Color(0, 0, 0, 1))  # 纯黑色
        self.top_scale_layer.add(Rectangle(pos=(left_mask_x, mask_y),
                                           size=(left_mask_width, mask_height)))

        # 右侧遮罩：覆盖右边多出的部分（例如，从 X = self.x + 168*HOUR_WIDTH 到 self.x + 169*HOUR_WIDTH）
        right_mask_x = self.x + 168 * HOUR_WIDTH
        right_mask_width = HOUR_WIDTH + 21  # 1小时宽度
        self.top_scale_layer.add(Color(0, 0, 0, 1))
        self.top_scale_layer.add(Rectangle(pos=(right_mask_x, mask_y),
                                           size=(right_mask_width, mask_height)))

    # routine_layer: all routine in drawing/scale region
    def _update_routine_layer(self, save_file=True):
        self.routine_layer.clear()
        for routine in self.routines.values():
            self._draw_routine(routine)
        if save_file:
            self.save_week_files("routine")

    # static_layer: grid, scale, hour label, etc.
    def _update_static_layer(self):
        self.static_layer.clear()
        # draw bottom scale region
        self.static_layer.add(Color(*hex_to_rgba(REGION_SCALE_BG_COLOR)))
        self.bottom_scale_region = Rectangle(pos=(self.x, self.y), size=(self.width, BOTTOM_SCALE_AREA_HEIGHT))
        self.static_layer.add(self.bottom_scale_region)

        # draw drawing region
        self.static_layer.add(Color(*hex_to_rgba(REGION_DRAWING_BG_COLOR)))
        self.drawing_region = Rectangle(pos=(self.x, self.y + BOTTOM_SCALE_AREA_HEIGHT),
                                        size=(self.width, DRAWING_AREA_HEIGHT))
        self.static_layer.add(self.drawing_region)

        # draw top scale region
        self.static_layer.add(Color(*hex_to_rgba(REGION_SCALE_BG_COLOR)))
        self.top_scale_region = Rectangle(pos=(self.x, self.y + BOTTOM_SCALE_AREA_HEIGHT + DRAWING_AREA_HEIGHT),
                                          size=(self.width, TOP_SCALE_AREA_HEIGHT))
        self.static_layer.add(self.top_scale_region)
        self.static_layer.add(Rectangle(pos=(self.x, self.y + BOTTOM_SCALE_AREA_HEIGHT + DRAWING_AREA_HEIGHT),
                                        size=(self.width, TOP_SCALE_AREA_HEIGHT)))

        # draw grid and hour labels
        num_hours = int(self.width // HOUR_WIDTH) + 1
        monday = self.get_current_week_monday()
        for i in range(num_hours - 1):
            x_line = self.x + i * HOUR_WIDTH
            self.static_layer.add(Color(*hex_to_rgba(REGION_LINE_COLOR)))
            y_pos = self.y
            y_top = self.y + self.height
            while y_pos < y_top:
                y_seg_end = min(y_pos + DASH_LENGTH, y_top)
                self.static_layer.add(Line(points=[x_line, y_pos, x_line, y_seg_end], width=1))
                y_pos += DASH_LENGTH * 2
            day_index = i // 24
            hour_in_day = i % 24
            label_x = x_line + 5
            drawing_top = self.y + BOTTOM_SCALE_AREA_HEIGHT + DRAWING_AREA_HEIGHT
            gap_center = drawing_top + (UPPER_SCALE_Y_VERSUS_TOP_SCALE_Y / 2)
            if hour_in_day == 0:
                date_for_day = monday + datetime.timedelta(days=day_index)
                label_text = f"{date_for_day.month}月{date_for_day.day}日"
            elif hour_in_day == 1:
                continue
            else:
                label_text = str(hour_in_day)
            core_label = CoreLabel(text=label_text, font_size=20, font_name=TEXTURE_FONT,
                                   color=hex_to_rgba(TEXTURE_FONT_COLOR))
            core_label.refresh()
            texture = core_label.texture
            label_y = gap_center - (texture.height / 2)
            self.static_layer.add(Color(1, 1, 1, 1))
            self.static_layer.add(Rectangle(texture=texture, pos=(label_x, label_y), size=texture.size))

        grid_bottom = self.y + BOTTOM_SCALE_AREA_HEIGHT
        grid_top = grid_bottom + DRAWING_AREA_HEIGHT
        x_pos, x_end = 0, TIMELINE_WIDTH
        self.static_layer.add(Color(*hex_to_rgba(REGION_LINE_COLOR)))
        while x_pos < TIMELINE_WIDTH:
            x_pos_end = min(x_pos + DASH_LENGTH, TIMELINE_WIDTH)
            self.static_layer.add(Line(points=[x_pos, grid_top, x_pos_end, grid_top], width=1))
            self.static_layer.add(Line(points=[x_pos, grid_bottom, x_pos_end, grid_bottom], width=1))
            x_pos += DASH_LENGTH * 2
        # self.static_layer.add(Color(*hex_to_rgba(REGION_LINE_COLOR)))
        # self.static_layer.add(Line(points=[self.x, grid_bottom, self.x + self.width, grid_bottom], width=1))
        # self.static_layer.add(Color(*hex_to_rgba(REGION_LINE_COLOR)))
        # self.static_layer.add(Line(points=[self.x, grid_top, self.x + self.width, grid_top], width=1))
        self.static_layer.add(Color(1, 1, 1, 1))

    # Drawing operations

    def _draw_poster(self):
        poster_width = 1.5 * HOUR_WIDTH  # 定义矩形宽度
        line_height = 2.2  # 控制文本行高

        for n in range(7):  # 7 个 24 小时刻度 (0, 24, 48, ..., 144)
            center_x = (24 * n + 0.5) * HOUR_WIDTH  # 目标中心位置 (24n+2) * HOUR_WIDTH

            # 计算矩形左上角位置
            rect_x = center_x - poster_width / 2

            # 绘制背景矩形
            self.event_layer.add(Color(0.11, 0.11, 0.11, 0.9))
            self.event_layer.add(Rectangle(pos=(rect_x, 0), size=(poster_width, TIMELINE_HEIGHT)))

            # 生成文本内容（多行，每个字符一行）
            text = "\n".join("一覽星河入夢來")

            core_label = CoreLabel(
                text=text,
                font_size=EVENT_FONT_SIZE * 1.5,
                font_name=STYLE_FONT,
                line_height=line_height,  # 你可在此调整行间距
                halign='center',
                valign='middle'
            )
            core_label.refresh()
            text_texture = core_label.texture
            text_size = text_texture.size  # (宽, 高)

            # 计算文本的左上角位置
            text_x = center_x - text_size[0] / 2
            text_y = TIMELINE_HEIGHT / 2 - text_size[1] / 2  # 确保垂直居中

            # 绘制文本
            self.event_layer.add(Color(1, 1, 1, 1))
            self.event_layer.add(Rectangle(texture=text_texture, pos=(text_x, text_y), size=text_size))

    def _draw_event(self, event: Event):
        ev_x = self.x + event.id * HALF_HOUR_WIDTH
        ev_y = EVENT_Y
        ev_height = EVENT_HEIGHT
        ev_width = HOUR_WIDTH if not event.is_half else HALF_HOUR_WIDTH

        color, text_color, border_color = map(hex_to_rgba, (event.color, event.text_color, event.border_color))
        color = (color[0], color[1], color[2], 0.7) if event.is_child else color

        self.event_layer.add(Color(*color))
        self.event_layer.add(Rectangle(pos=(ev_x, ev_y), size=(ev_width, ev_height)))
        self.event_layer.add(Color(*border_color))
        self.event_layer.add(Line(rectangle=(ev_x, ev_y, ev_width, ev_height), width=event.border_thickness))

        if not event.is_half:
            vertical_text = "\n".join(list(event.name))
            core_label = CoreLabel(text=vertical_text,
                                   font_size=EVENT_FONT_SIZE,
                                   font_name=EVENT_FONT,
                                   color=text_color,
                                   markup=True)
            core_label.refresh()
            texture = core_label.texture
            text_x = ev_x + (ev_width - texture.width) / 2
            text_y = ev_y + ev_height - EVENT_TEXT_UPPER_PADDING - texture.height
            self.event_layer.add(Color(1, 1, 1, 1))
            self.event_layer.add(Rectangle(texture=texture, pos=(text_x, text_y), size=texture.size))

        if event.is_stamped and event.stamp_name:
            stamp_texture = self.half_stamp_images.get(event.stamp_name, None) if event.is_half else \
                self.stamp_images.get(event.stamp_name, None)
            if stamp_texture is None:
                event.unstamp()
            else:
                original_size = HALF_STAMP_SIZE if event.is_half else STAMP_SIZE
                scaled_size = SCALED_HALF_STAMP_SIZE if event.is_half else SCALED_STAMP_SIZE
                center_x, center_y = ev_x + original_size[0] / 2, ev_y + original_size[1] / 2
                stamp_pos = (center_x - scaled_size[0] / 2, center_y - scaled_size[1] / 2)

                self.event_layer.add(Color(1, 1, 1, 1))
                self.event_layer.add(Rectangle(texture=stamp_texture, pos=stamp_pos,
                                               size=scaled_size))

    def _draw_routine(self, routine: Routine):
        rt_x = self.x + routine.id * HALF_HOUR_WIDTH
        rt_y = ROUTINE_Y
        rt_height = ROUTINE_HEIGHT
        rt_width = ROUTINE_WIDTH

        color, text_color, border_color = map(hex_to_rgba, (routine.color, routine.text_color, routine.border_color))

        self.routine_layer.add(Color(*color))
        self.routine_layer.add(Rectangle(pos=(rt_x, rt_y), size=(rt_width, rt_height)))
        self.routine_layer.add(Color(*border_color))
        self.routine_layer.add(Line(rectangle=(rt_x, rt_y, rt_width, rt_height), width=routine.border_thickness))

        vertical_text = "\n".join(routine.name)
        core_label = CoreLabel(text=vertical_text,
                               halign="center",
                               font_size=ROUTINE_FONT_SIZE,
                               font_name=EVENT_FONT,
                               color=text_color,
                               line_height=routine.line_height)
        core_label.refresh()
        texture = core_label.texture
        text_x = rt_x + (rt_width - texture.width) / 2
        text_y = ROUTINE_TEXT_Y + (ROUTINE_TEXT_Y_MAX - ROUTINE_TEXT_Y - texture.height) / 2
        self.routine_layer.add(Color(1, 1, 1, 1))
        self.routine_layer.add(Rectangle(texture=texture, pos=(text_x, text_y), size=texture.size))

    # User interactions
    def on_touch_down(self, touch):

        if self.collide_point(*touch.pos):
            log(f"touch on TimelineWidget: {touch.pos}", "blue")
            local_x = touch.x - self.x
            local_y = touch.y - self.y

            clicked_cell = int(local_x // HALF_HOUR_WIDTH)

            # touch on bottom scale region -> show routine dialog
            if local_y < BOTTOM_SCALE_AREA_HEIGHT:
                routine = self.get_cell_routine(clicked_cell)
                log(f"touch on routine area : {routine}", "blue")
                self.show_routine_dialog(routine=routine,
                                         start_cell=clicked_cell)

            # touch on drawing region -> create, stamp or modify event
            elif BOTTOM_SCALE_AREA_HEIGHT <= local_y < BOTTOM_SCALE_AREA_HEIGHT + DRAWING_AREA_HEIGHT:
                log(f"touch on drawing region: {clicked_cell}", "blue")
                event = self.get_cell_event(clicked_cell)

                if event is None:  # create new event
                    log(f"touch on empty cell: {clicked_cell}", "blue")
                    self.show_event_dialog(start_cell=clicked_cell)

                else:  # touch on existing event
                    log(f"touch on existing {event}", "blue")
                    ev_x = self.x + event.id * HALF_HOUR_WIDTH
                    ev_y = self.y + BOTTOM_SCALE_AREA_HEIGHT
                    stamp_width = STAMP_WIDTH if not event.is_half else HALF_STAMP_WIDTH

                    # touch on stamp area of event
                    if local_x <= touch.x <= ev_x + stamp_width and ev_y <= touch.y <= ev_y + STAMP_HEIGHT:
                        log(f"touch on stamp area of event: {event.id}", "blue")
                        event.stamp(stamp_name=self.selected_stamp, half_stamp_name=self.selected_half_stamp
                                    ) if not event.is_stamped else event.unstamp()
                        self._update_event_layer(save_file=True)

                    else:  # touch on dialog area of event
                        log(f"touch on dialog area of event: {event.id}", "blue")
                        self.show_event_dialog(event=event)

            return

        return super(TimelineWidget, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        return super(TimelineWidget, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        return super(TimelineWidget, self).on_touch_up(touch)

    # def show_event_context_menu(self, event):
    #     menu_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
    #     btn_modify = Button(text="修改", font_name=BUTTON_FONT, size_hint_y=None, height=40)
    #     btn_delete = Button(text="删除", font_name=BUTTON_FONT, size_hint_y=None, height=40)
    #     btn_cancel = Button(text="取消", font_name=BUTTON_FONT, size_hint_y=None, height=40)
    #     menu_layout.add_widget(btn_modify)
    #     menu_layout.add_widget(btn_delete)
    #     menu_layout.add_widget(btn_cancel)
    #     popup = Popup(title="事件操作", title_font=TITLE_FONT, title_size=25, content=menu_layout,
    #                   size_hint=(None, None), size=EVENT_CONTENT_MENU_SIZE, auto_dismiss=False)
    #
    #     def on_cancel(instance):
    #         popup.dismiss()
    #
    #     def on_delete(instance):
    #         if event.is_child:  # if child, parent remove child
    #             event.parent.remove_child()
    #         elif event.is_parent:  # remove child if exists
    #             self.events.pop(event.child.id)
    #
    #         self.events.pop(event.id)  # remove event
    #
    #         self._update_event_layer()
    #         popup.dismiss()
    #
    #     def on_modify(instance):
    #         popup.dismiss()
    #         self.show_event_dialog(event=event)
    #
    #     btn_cancel.bind(on_release=on_cancel)
    #     btn_delete.bind(on_release=on_delete)
    #     btn_modify.bind(on_release=on_modify)
    #     popup.open()

    # Event interactions UI
    def create_color_picker_row(self, label_text, initial_color, update_var,
                                label_color=DIALOG_LABEL_RGB, background_color=DIALOG_BG_RGB):

        layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=10)
        label = Label(text=label_text, size_hint_x=None, width=100, font_name=LABEL_FONT)
        button = Button(background_normal='', background_color=hex_to_rgba(initial_color),
                        size_hint_x=None, width=40)
        text_input = TextInput(text=initial_color, multiline=False, size_hint_x=None, width=150,
                               font_name=COLOR_INPUT_FONT)

        # 当在文本框中输入并回车时，验证 HEX 格式，并更新颜色按钮的颜色
        def on_text_validate(instance):
            hex_str = instance.text.strip()
            if len(hex_str) == 7 and hex_str.startswith('#'):
                button.background_color = hex_to_rgba(hex_str)
                update_var[0] = hex_str  # 更新局部变量
                self.add_recent_color(hex_str)
            else:
                instance.text = update_var[0]

        text_input.bind(on_text_validate=on_text_validate)

        # 点击颜色按钮时打开颜色选择器
        def open_color_picker(instance):
            # 调用已有的 get_color_picker_widget 方法获取颜色选择器相关控件
            color_picker_container, cp, hex_input = self.get_color_picker_widget(hex_to_rgba(update_var[0]))
            picker_popup = Popup(title="选择颜色", title_font=TITLE_FONT, content=color_picker_container,
                                 size_hint=(None, None), size=COLOR_PICKER_SIZE, auto_dismiss=False)

            def on_confirm(instance):
                chosen_color = rgb_to_hex(cp.color)
                button.background_color = hex_to_rgba(chosen_color)
                text_input.text = chosen_color
                update_var[0] = chosen_color  # 更新局部变量
                self.add_recent_color(chosen_color)
                picker_popup.dismiss()

            confirm_btn = Button(text="确定", size_hint_y=None, height=40, font_name=BUTTON_FONT)
            confirm_btn.bind(on_release=on_confirm)
            color_picker_container.add_widget(confirm_btn)
            picker_popup.open()

        button.bind(on_release=open_color_picker)

        layout.add_widget(label)
        layout.add_widget(button)
        layout.add_widget(text_input)
        return layout

    @staticmethod
    def create_checkbox(label_text,
                        initial_state,
                        update_var,
                        spacing=CHECKBOX_SPACING,
                        checkbox_size=CHECKBOX_SIZE,
                        label_width=CHECKBOX_LABEL_WIDTH,
                        label_height=CHECKBOX_LABEL_HEIGHT,
                        outer_height=CHECKBOX_OUTER_HEIGHT):
        # 内部布局：将 checkbox 和 label 紧密排列（spacing=0）
        inner_layout = BoxLayout(orientation='horizontal', spacing=spacing, size_hint=(None, None), height=40)

        checkbox = CheckBox(
            active=initial_state,
            size_hint=(None, None),
            size=checkbox_size,
            right=True
        )
        label = Label(
            text=label_text,
            font_name=CHECKBOX_LABEL_FONT,
            halign="left",
            valign="middle",
            size_hint=(None, None),
            width=label_width,
            height=label_height,
            padding=(0, 0)
        )
        # 绑定 size 使 halign/valign 生效
        label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        def on_checkbox_change(instance, value):
            update_var[0] = value  # 将新的状态存入 update_var[0]

        checkbox.bind(active=on_checkbox_change)

        inner_layout.add_widget(checkbox)
        inner_layout.add_widget(label)

        # 设置 inner_layout 的宽度为 checkbox + label 的宽度
        inner_layout.width = checkbox.width + label.width

        # 外部 AnchorLayout 用于整体居中
        outer_layout = AnchorLayout(
            anchor_x='center',  # 居中对齐
            anchor_y='center',
            size_hint_y=None,
            height=outer_height
        )
        outer_layout.add_widget(inner_layout)

        return outer_layout, checkbox

    def show_event_dialog(self, event: Event = None, start_cell=None):
        log(f"show_event_dialog: event={event.id if event else None}", "purple")
        assert (event is not None or start_cell is not None) and not (event and start_cell), \
            "only one of event and start_cell should be provided"

        if event is None:
            event_id = start_cell
            name = "事件名称"
            color = "#FFFFFF"
            text_color = "#000000"
            border_color = EVENT_BORDER_COLOR
            is_half = False
            is_child = False
            child_id = None
            is_parent = False
        else:
            event_id = event.id
            name = event.name
            color = event.color
            text_color = event.text_color
            border_color = event.border_color
            is_half = event.is_half
            is_child = event.is_child
            is_parent = event.is_parent
            child_id = event.child_id

        background_color = hex_to_rgba(color)
        background_color = (background_color[0], background_color[1], background_color[2], BACKGROUND_TRANSPARENCY)
        if event is None:
            background_color = DIALOG_BG_RGB

        # UI 组件
        popup_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        info_label = Label(text=f"{self.get_time_string(event_id)}", size_hint_y=None, height=30, font_name=LABEL_FONT)
        popup_layout.add_widget(info_label)
        name_input = TextInput(text=name, multiline=False, size_hint_y=None, height=40, font_name=TEXT_INPUT_FONT)
        popup_layout.add_widget(name_input)

        color_var, text_color_var, border_color_var = [color], [text_color], [border_color]
        popup_layout.add_widget(self.create_color_picker_row("事件颜色", color, color_var))
        popup_layout.add_widget(self.create_color_picker_row("文本颜色", text_color, text_color_var))
        popup_layout.add_widget(self.create_color_picker_row("边框颜色", border_color, border_color_var))

        # 假设 is_half 与 is_child 为已有的布尔变量，记录初始状态
        is_half_var = [is_half]
        is_child_var = [is_child]
        is_parent_var = [is_parent]
        repeat_var = [False]
        clear_repeat_var = [False]

        # 创建复选框控件，并获取对应的 CheckBox 对象
        half_layout, half_checkbox = self.create_checkbox("半小时", is_half, is_half_var)
        child_layout, child_checkbox = self.create_checkbox("非独立", is_child, is_child_var)
        parent_layout, parent_checkbox = self.create_checkbox("被延长", is_parent, is_parent_var)
        repeat_layout, _ = self.create_checkbox("周内重复", False, repeat_var)
        clear_repeat_layout, _ = self.create_checkbox("清除重复", False, clear_repeat_var)

        next_occu, next_next_occu = self.is_cell_occupied(event_id + 1), self.is_cell_occupied(event_id + 2)

        # get previous and next event id if they exist, or False
        log(f"next_occu: {next_occu}", "purple")
        if next_occu and next_occu != event_id:
            # if both next cell are occupied, and next cell is not the same as current cell,
            # then this cell can only be a half cell, we disable the checkbox and set it to True
            is_half_var = [True]
            half_checkbox.active = True
            half_checkbox.disabled = True

        lock_parent_checkbox = False
        if next_next_occu and next_next_occu != child_id:
            # if next next cell is occupied, and next next cell is not the same as child cell,
            # then this cell can not be a parent cell, we disable the checkbox and set it to False
            is_parent_var = [False]
            parent_checkbox.active = False
            parent_checkbox.disabled = True
            lock_parent_checkbox = True

        # 添加到总的 popup 布局中
        popup_layout.add_widget(half_layout)
        popup_layout.add_widget(child_layout)
        popup_layout.add_widget(parent_layout)
        popup_layout.add_widget(repeat_layout)
        popup_layout.add_widget(clear_repeat_layout)

        # 绑定“半小时”复选框的状态变化，控制“非独立”的可用性
        def update_child_checkbox(instance, value):
            # 当“半小时”被勾选时，“非独立”才可用，否则禁用并取消选中
            child_checkbox.disabled = not value
            if not value:
                child_checkbox.active = False

        def update_parent_checkbox(instance, value):
            # 当“半小时”不被勾选时，“被延长”才可用，否则禁用并取消选中
            parent_checkbox.disabled = (value or lock_parent_checkbox)
            if value:
                parent_checkbox.active = False

        half_checkbox.bind(active=update_child_checkbox)
        half_checkbox.bind(active=update_parent_checkbox)
        # 设置初始状态
        update_child_checkbox(half_checkbox, half_checkbox.active)
        update_parent_checkbox(half_checkbox, half_checkbox.active)

        # 按钮布局及其它 UI 部分保持不变
        btn_layout = BoxLayout(size_hint_y=None, height=40, spacing=10)
        btn_confirm = Button(text="确定", font_name=BUTTON_FONT)
        btn_layout.add_widget(btn_confirm)
        btn_delete = Button(text="删除", font_name=BUTTON_FONT) if event is not None else Widget(size_hint_x=1)
        btn_layout.add_widget(btn_delete)
        btn_cancel = Button(text="取消", font_name=BUTTON_FONT)
        btn_layout.add_widget(btn_cancel)
        popup_layout.add_widget(btn_layout)

        popup = Popup(title="事件" + ("创建" if event is None else "修改"),
                      title_font=TITLE_FONT,
                      title_size=30,
                      content=popup_layout,
                      size_hint=(None, None),
                      size=EVENT_DIALOG_SIZE,
                      auto_dismiss=False,
                      background_color=background_color)

        def on_confirm(instance):
            log(f"on_confirm, is_half:{is_half}, {is_half_var}", "purple")
            if event is None:  # new event
                new_event = self._create_new_event(event_id=event_id, name=name_input.text, color=color_var[0],
                                                   text_color=text_color_var[0], border_color=border_color_var[0],
                                                   is_half=is_half_var[0], is_child=is_child_var[0],
                                                   is_parent=is_parent_var[0], popup=popup)
                if repeat_var[0]:
                    self.week_repeat(event=new_event)
                if clear_repeat_var[0]:
                    self.clear_week_repeat(event=new_event)
            else:
                new_event = self._modify_event(event=event, name=name_input.text, color=color_var[0],
                                               text_color=text_color_var[0],
                                               border_color=border_color_var[0], is_half=is_half_var[0],
                                               is_child=is_child_var[0], is_parent=is_parent_var[0], popup=popup)
                if repeat_var[0]:
                    self.week_repeat(event=new_event)
                if clear_repeat_var[0]:
                    self.clear_week_repeat(event=new_event)

            self._update_event_layer()
            popup.dismiss()

        def on_delete(instance):
            if event is not None:
                event.remove_self()
                self._update_event_layer()
            popup.dismiss()

        btn_confirm.bind(on_release=on_confirm)
        btn_cancel.bind(on_release=lambda instance: popup.dismiss())
        btn_delete.bind(on_release=on_delete)

        popup.open()

    def show_routine_dialog(self, routine: Routine = None, start_cell=None, ):
        assert (routine is not None or start_cell is not None), "routine or start_cell should be provided"
        if routine is None:
            routine_id = start_cell
            name = "区间"
            color = "#FFFFFF"
            text_color = "#000000"
            border_color = "#000000"
            line_height = ROUTINE_LINE_HEIGHT
        else:
            routine_id = routine.id
            name = routine.name
            color = routine.color
            text_color = routine.text_color
            border_color = routine.border_color
            line_height = routine.line_height if routine.line_height else ROUTINE_LINE_HEIGHT

        background_color = hex_to_rgba(color)
        background_color = (background_color[0], background_color[1], background_color[2], BACKGROUND_TRANSPARENCY)
        if routine is None:
            background_color = DIALOG_BG_RGB

        # UI 组件
        popup_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        info_label = Label(text=f"{self.get_time_string(routine_id)}", size_hint_y=None, height=30,
                           font_name=LABEL_FONT)
        popup_layout.add_widget(info_label)

        name_input = TextInput(text=name, multiline=False, size_hint_y=None, height=40, font_name=TEXT_INPUT_FONT)
        popup_layout.add_widget(name_input)

        line_height_input = TextInput(text=str(line_height), multiline=False, size_hint_y=None, height=40,)
        popup_layout.add_widget(line_height_input)

        color_var, text_color_var, border_color_var = [color], [text_color], [border_color]
        popup_layout.add_widget(self.create_color_picker_row("区间颜色", color, color_var))
        popup_layout.add_widget(self.create_color_picker_row("文字颜色", text_color, text_color_var))
        popup_layout.add_widget(self.create_color_picker_row("边框颜色", border_color, border_color_var))

        repeat_var = [False]
        clear_repeat_var = [False]
        repeat_layout, _ = self.create_checkbox("周内重复", False, repeat_var)
        clear_repeat_layout, _ = self.create_checkbox("清除重复", False, clear_repeat_var)

        popup_layout.add_widget(repeat_layout)
        popup_layout.add_widget(clear_repeat_layout)

        btn_layout = BoxLayout(size_hint_y=None, height=40, spacing=10)
        btn_confirm = Button(text="确定", font_name=BUTTON_FONT)
        btn_layout.add_widget(btn_confirm)
        btn_delete = Button(text="删除", font_name=BUTTON_FONT) if routine is not None else Widget(size_hint_x=1)
        btn_layout.add_widget(btn_delete)
        btn_cancel = Button(text="取消", font_name=BUTTON_FONT)
        btn_layout.add_widget(btn_cancel)
        popup_layout.add_widget(btn_layout)
        popup = Popup(title="区间" + ("创建" if routine is None else "修改"),
                      title_font=TITLE_FONT,
                      title_size=30,
                      content=popup_layout,
                      size_hint=(None, None),
                      size=ROUTINE_DIALOG_SIZE,
                      auto_dismiss=False,
                      background_color=background_color)

        def on_confirm(instance):
            try:
                line_height_float = float(line_height_input.text)
            except:
                line_height_float = ROUTINE_LINE_HEIGHT
            if routine is None:  # new routine
                new_routine = self._create_new_routine(routine_id=routine_id, text=name_input.text, color=color_var[0],
                                                       text_color=text_color_var[0], border_color=border_color_var[0],
                                                       border_thickness=ROUTINE_BORDER_THICKNESS, line_height=line_height_float)
                if repeat_var[0]:
                    self.week_repeat(routine=new_routine)
                if clear_repeat_var[0]:
                    self.clear_week_repeat(routine=new_routine)

            else:
                new_routine = self._modify_routine(routine=routine, text=name_input.text, color=color_var[0],
                                                   text_color=text_color_var[0], border_color=border_color_var[0],
                                                   border_thickness=ROUTINE_BORDER_THICKNESS, line_height=line_height_float)
                if repeat_var[0]:
                    self.week_repeat(routine=new_routine)
                if clear_repeat_var[0]:
                    self.clear_week_repeat(routine=new_routine)

            self._update_layers(update_routine=True, save_routine=True, update_top_scale=True, update_event=True)
            popup.dismiss()

        def on_delete(instance):
            if routine is not None:
                routine.remove_self()
                self._update_layers(update_routine=True, save_routine=True, update_top_scale=True, update_event=True)
            popup.dismiss()

        btn_confirm.bind(on_release=on_confirm)
        btn_cancel.bind(on_release=lambda instance: popup.dismiss())
        btn_delete.bind(on_release=on_delete)

        popup.open()


# ---------------------------
# RootWidget 和 MyApp 保持不变
from kivy.core.window import Window

from functools import partial
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window

# 假设其它模块和常量（如 TIMELINE_HEIGHT, FUNCTION_AREA_HEIGHT, HOUR_WIDTH 等）已正确导入

from functools import partial
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
# 假设 TIMELINE_HEIGHT, TIMELINE_WIDTH, FUNCTION_AREA_HEIGHT, HOUR_WIDTH,
# hex_to_rgba, STAMP_BUTTON_WIDTH, STAMP_BUTTON_HEIGHT, STAMP_BUTTON_SPACING,
# STAMP_ACTIVE_COLOR, STAMP_INACTIVE_COLOR 等均已在 defines.py 中定义并正确导入

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from functools import partial


class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super(RootWidget, self).__init__(**kwargs)
        self.orientation = 'vertical'
        # 创建滚动区域及 TimelineWidget（代码保持不变）
        self.scrollview = ScrollView(do_scroll_x=True, do_scroll_y=False, size_hint_y=None, height=TIMELINE_HEIGHT)
        self.timeline = TimelineWidget(size_hint=(None, None), size=(TIMELINE_WIDTH, TIMELINE_HEIGHT))
        self.scrollview.add_widget(self.timeline)
        self.add_widget(self.scrollview)

        # 请求全局键盘
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        if self._keyboard:
            self._keyboard.bind(on_key_down=self.on_key_down)

        # 默认选中各自的印章
        if self.timeline.stamp_images:
            self.timeline.selected_stamp = list(self.timeline.stamp_images.keys())[0]
        else:
            self.timeline.selected_stamp = None
        if self.timeline.half_stamp_images:
            self.timeline.selected_half_stamp = list(self.timeline.half_stamp_images.keys())[0]
        else:
            self.timeline.selected_half_stamp = None

        # 第一行：全时印章按钮
        normal_area = BoxLayout(orientation='horizontal', size_hint_y=None, height=STAMP_BUTTON_SIZE,
                                spacing=STAMP_BUTTON_SPACING, padding=0)
        self.stamp_buttons = []  # 保存全时印章按钮
        for stamp_name, texture in self.timeline.stamp_images.items():
            stamp_btn = StampButton(stamp_name, texture,
                                    size_hint=(None, None),
                                    size=(STAMP_BUTTON_SIZE, STAMP_BUTTON_SIZE))
            stamp_btn.bind(on_release=partial(self.on_stamp_select, stamp_name=stamp_name))
            self.stamp_buttons.append(stamp_btn)
            normal_area.add_widget(stamp_btn)
        self.add_widget(normal_area)

        # 第二行：半小时印章按钮
        half_area = BoxLayout(orientation='horizontal', size_hint_y=None, height=STAMP_BUTTON_SIZE,
                              spacing=STAMP_BUTTON_SPACING, padding=0)
        self.half_stamp_buttons = []  # 保存半小时印章按钮
        for stamp_name, texture in self.timeline.half_stamp_images.items():
            stamp_btn = StampButton(stamp_name, texture,
                                    size_hint=(None, None),
                                    size=(STAMP_BUTTON_SIZE, STAMP_BUTTON_SIZE))
            stamp_btn.bind(on_release=partial(self.on_half_stamp_select, stamp_name=stamp_name))
            self.half_stamp_buttons.append(stamp_btn)
            half_area.add_widget(stamp_btn)
        self.add_widget(half_area)

        # 绑定滚动及其它事件（保持不变）
        self.scrollview.bind(on_touch_down=self.on_scrollview_touch_down)
        Window.bind(on_window_touch_up=self.on_window_touch_up)

        # 初始化时更新按钮高亮背景
        self.update_stamp_buttons()
        self.update_half_stamp_buttons()


    def on_stamp_select(self, instance, stamp_name):
        self.timeline.selected_stamp = stamp_name
        self.update_stamp_buttons()

    def on_half_stamp_select(self, instance, stamp_name):
        self.timeline.selected_half_stamp = stamp_name
        self.update_half_stamp_buttons()

    def update_stamp_buttons(self):
        for btn in self.stamp_buttons:
            if btn.stamp_name == self.timeline.selected_stamp:
                btn.background_color = hex_to_rgba(FULL_STAMP_ACTIVE_COLOR)
            else:
                btn.background_color = hex_to_rgba(STAMP_INACTIVE_COLOR)

    def update_half_stamp_buttons(self):
        for btn in self.half_stamp_buttons:
            if btn.stamp_name == self.timeline.selected_half_stamp:
                btn.background_color = hex_to_rgba(HALF_STAMP_ACTIVE_COLOR)
            else:
                btn.background_color = hex_to_rgba(STAMP_INACTIVE_COLOR)

    # 其它滚动、事件处理代码保持不变……

    def on_scrollview_touch_down(self, instance, touch):
        if self.scrollview.collide_point(*touch.pos):
            log(f"touch on scrollview: {touch.pos}", "blue")
            self._initial_scroll_x = self.scrollview.scroll_x
        return False

    def on_window_touch_up(self, window, touch):
        # 保持原有滚动及周切换逻辑
        if not self.scrollview.collide_point(*touch.pos):
            return False
        if not hasattr(self, "_initial_scroll_x") or self._initial_scroll_x is None:
            return False
        final_scroll_x = self.scrollview.scroll_x
        if self._initial_scroll_x < 0.02 and final_scroll_x < -0.05:
            self.timeline.current_week_offset -= 1
            self.timeline.load_events_from_file()
            self.timeline._update_static()
            Clock.schedule_once(lambda dt: self.timeline.center_on_current_hour(), 0.1)
        elif self._initial_scroll_x > 0.98 and final_scroll_x > 1.05:
            self.timeline.current_week_offset += 1
            self.timeline.load_events_from_file()
            self.timeline._update_static()
            Clock.schedule_once(lambda dt: self.timeline.center_on_current_hour(), 0.1)
        self._initial_scroll_x = None
        return False

    def _keyboard_closed(self):
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self.on_key_down)
            self._keyboard = None

    def on_key_down(self, keyboard, keycode, text, modifiers):
        # keycode 是一个元组，例如 (32, 'spacebar')
        print("on_key_down:", keycode, text, modifiers)  # 用于调试，确认事件是否触发
        if keycode[0] == 32:  # 32 对应空格键
            if hasattr(self, "timeline") and hasattr(self.timeline, "slide_to_current_hour"):
                self.timeline.slide_to_current_hour()
                print("空格键按下，视图移动到当前小时位置")
        return True


class MyApp(App):
    title = "Anyway 我先放几个 TODO 在这里"
    icon = "resources/icon.png"
    def build(self):
        return RootWidget()


if __name__ == '__main__':
    MyApp().run()
