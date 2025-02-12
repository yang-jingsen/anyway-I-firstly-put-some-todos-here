from __future__ import annotations

from dataclasses import dataclass
from defines import EVENT_BORDER_THICKNESS, EVENT_BORDER_COLOR, ROUTINE_BORDER_THICKNESS


@dataclass
class Stamp:
    def __init__(self,
                 stamp_name: str,
                 is_half_stamp: bool = False,
                 stamp_file: str = None, ):
        self.stamp_name = stamp_name
        self.is_half_stamp = is_half_stamp
        self.stamp_file = stamp_file


@dataclass
class Event:
    def __init__(self,
                 event_id: int,
                 name: str,
                 color: str,
                 text_color: str,
                 border_color: str = EVENT_BORDER_COLOR,
                 border_thickness: int = EVENT_BORDER_THICKNESS,
                 is_half: bool = False,
                 is_child: bool = False,
                 parent: Event = None,
                 parent_id: int = None,
                 is_parent: bool = False,
                 child: Event = None,
                 child_id: int = None,
                 is_stamped: bool = False,
                 stamp_name: str = None,
                 events_dict: dict = None):
        self.id = event_id
        self.name = name
        self.color = color
        self.text_color = text_color
        self.border_color = border_color
        self.border_thickness = border_thickness
        self.is_half = is_half
        self.is_child = is_child
        self.parent = parent
        self.parent_id = parent_id
        self.is_parent = is_parent
        self.child = child
        self.child_id = child_id
        self.is_stamped = is_stamped
        self.stamp_name = stamp_name
        self.events_dict = events_dict

    def __str__(self):
        return (f"Event {self.id}: {self.name}, colors: {self.color}, {self.text_color}, {self.border_color}, "
                f"border: {self.border_thickness}\n"
                f"is_half: {self.is_half}, is_stamped: {self.is_stamped}, stamp_name: {self.stamp_name}\n"
                f"is_child: {self.is_child}, parent_id: {self.parent_id}, parent: {self.parent is not None}\n"
                f"is_parent: {self.is_parent}, child_id: {self.child_id}, child: {self.child is not None}\n")

    def assign_events_dict(self, events_dict):
        self.events_dict = events_dict

    def assign_child_and_parent(self):
        if self.parent_id:
            self.parent = self.events_dict.get(self.parent_id)
        if self.child_id:
            self.child = self.events_dict.get(self.child_id)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'text_color': self.text_color,
            'border_color': self.border_color,
            'border_thickness': self.border_thickness,
            'is_half': self.is_half,
            'is_child_event': self.is_child,
            'parent_id': self.parent_id,
            'is_parent_event': self.is_parent,
            'child_id': self.child_id,
            'is_stamped': self.is_stamped,
            'stamp_name': self.stamp_name,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            event_id=data['id'],
            name=data['name'],
            color=data['color'],
            text_color=data['text_color'],
            border_color=data['border_color'],
            border_thickness=data['border_thickness'],
            is_half=data['is_half'],
            is_child=data['is_child_event'],
            parent_id=data['parent_id'],
            is_parent=data['is_parent_event'],
            child_id=data['child_id'],
            is_stamped=data['is_stamped'],
            stamp_name=data['stamp_name']
        )

    def become_full(self):
        if not self.is_half:
            return
        if self.is_child:  # full event is not child event
            self.parent.remove_child(chained_call=True)
        self.is_half = False
        self.is_child = False
        self.parent_id = None
        self.is_parent = False
        self.child_id = None
        self.is_stamped = False
        self.stamp_name = None

    def become_half(self):
        if self.is_half:
            return
        if self.is_parent:  # half event is not parent event
            self.child.remove_parent(chained_call=True)
        self.is_half = True
        self.is_child = False
        self.parent_id = None
        self.is_parent = False
        self.child_id = None
        self.is_stamped = False
        self.stamp_name = None

    def add_parent(self, parent: Event = None, parent_id: int = None, half_stamp_name=None, chained_call=False):
        assert parent or parent_id, "parent or parent_id must be provided"
        assert not (parent and parent_id), "only one of parent or parent_id should be provided"
        assert half_stamp_name, "half_stamp_name must be provided"
        if self.is_child:
            return

        self.is_child = True
        if parent:
            self.parent = parent
            self.parent_id = parent.id
        else:
            self.parent = self.events_dict.get(parent_id)
            self.parent_id = parent_id
        self.name = self.parent.name
        self.color = self.parent.color
        self.text_color = self.parent.text_color
        self.border_color = self.parent.border_color
        self.is_stamped = self.parent.is_stamped
        self.stamp_name = half_stamp_name if self.is_stamped else None

        if not chained_call:
            self.parent.add_child(self, chained_call=True, half_stamp_name=half_stamp_name)

    def add_child(self, child: Event = None, child_id: int = None, half_stamp_name=None, chained_call=False):
        assert child or child_id, "child or child_id must be provided"
        assert not (child and child_id), "only one of child or child_id should be provided"
        if self.is_parent:
            return

        self.is_parent = True
        if child:
            self.child = child
            self.child_id = child.id
        else:
            self.child = self.events_dict.get(child_id)
            self.child_id = child_id

        if not chained_call:
            self.child.add_parent(self, half_stamp_name=half_stamp_name, chained_call=True)

    def remove_child(self, chained_call=False):
        if not self.is_parent:
            return
        if not chained_call:
            self.child.remove_parent(chained_call=True)

        self.is_parent = False
        self.child_id = None
        self.child = None

    def remove_parent(self, chained_call=False):
        if not self.is_child:
            return
        if not chained_call:
            self.parent.remove_child(chained_call=True)

        self.is_child = False
        self.parent_id = None
        self.parent = None

    def stamp(self, stamp_name: str = None, half_stamp_name: str = None, chained_call=False):
        self.is_stamped = True
        self.stamp_name = stamp_name if not self.is_half else half_stamp_name
        if not chained_call:
            if self.is_parent:
                self.child.stamp(half_stamp_name=half_stamp_name, chained_call=True)
            if self.is_child:
                self.parent.stamp(stamp_name=stamp_name, chained_call=True)

    def unstamp(self, chained_call=False):
        self.is_stamped = False
        self.stamp_name = None
        if not chained_call:
            if self.is_parent:
                self.child.unstamp(chained_call=True)
            if self.is_child:
                self.parent.unstamp(chained_call=True)

    def remove_self(self, chained_call=False):
        if not chained_call:
            if self.is_parent:
                self.remove_child(chained_call=True)
            if self.is_child:
                self.parent.remove_child(chained_call=True)
        self.events_dict.pop(self.id)

    def copy_event(self, new_event_id):
        self.events_dict[new_event_id] = Event(
            event_id=new_event_id,
            name=self.name,
            color=self.color,
            text_color=self.text_color,
            border_color=self.border_color,
            border_thickness=self.border_thickness,
            is_half=self.is_half,
            events_dict=self.events_dict
        )

    def clear_copy(self, tar: Event = None, tar_id: int = None):
        assert (tar or tar_id) and not (tar and tar_id), "only one of tar or tar_id should be provided"
        tar = tar if tar else self.events_dict.get(tar_id, None)
        if tar and self.name == tar.name and \
                self.color == tar.color and \
                self.text_color == tar.text_color and \
                self.is_half == tar.is_half:
            tar.remove_self()


@dataclass
class Routine:
    def __init__(self,
                 routine_id: int,
                 name: str,
                 color: str,
                 text_color: str,
                 border_color: str,
                 border_thickness: int = ROUTINE_BORDER_THICKNESS,
                 line_height: float = 1.5,
                 routines_dict: dict = None):
        self.id = routine_id
        self.name = name
        self.text_color = text_color
        self.border_color = border_color
        self.color = color
        self.border_thickness = border_thickness
        self.line_height = float(line_height)
        self.routines_dict = routines_dict

    def __str__(self):
        return (f"Routine {self.id}: {self.name}, colors: {self.color}, {self.text_color}, {self.border_color}, "
                f"routines_dict: {self.routines_dict is not None}\n")

    def assign_routines_dict(self, routines_dict):
        self.routines_dict = routines_dict

    def to_dict(self):
        return {
            'id': self.id,
            'text': self.name,
            'text_color': self.text_color,
            'border_color': self.border_color,
            'color': self.color,
            'line_height': self.line_height
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            routine_id=data['id'],
            name=data['text'],
            color=data.get('color', "#FFFFFF"),
            text_color=data.get('text_color', "#000000"),
            border_color=data.get('border_color', "#000000"),
            line_height=data.get('line_height', 1.5)
        )

    def remove_self(self):
        self.routines_dict.pop(self.id)

    def copy_routine(self, new_routine_id):
        self.routines_dict[new_routine_id] = Routine(
            routine_id=new_routine_id,
            name=self.name,
            color=self.color,
            text_color=self.text_color,
            border_color=self.border_color,
            line_height=self.line_height,
            routines_dict=self.routines_dict
        )

    def clear_copy(self, tar: Routine = None, tar_id: int = None):
        assert (tar or tar_id) and not (tar and tar_id), "only one of tar or tar_id should be provided"
        tar = tar if tar else self.routines_dict.get(tar_id, None)
        if tar and self.name == tar.name and \
                self.color == tar.color and \
                self.text_color == tar.text_color:
            tar.remove_self()