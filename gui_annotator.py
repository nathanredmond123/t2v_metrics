#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple, Dict

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

SKILL_OPTIONS = [
    "occlusion_visibility",
    "distance_awareness",
    "navigation",
    "relative_agents",
    "egocentric_motion",
]

IMG_EXTS = {".jpg", ".jpeg", ".png"}


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def list_image_sets(img_dir: Path) -> List[List[str]]:
    """
    Group images by prefix before the first underscore, e.g.:

        0_a.jpg, 0_b.jpg, 0_c.jpg, 0_d.jpg --> set "0"

    Returns a list of sets, where each set is a list of filenames.
    """
    groups: Dict[str, List[str]] = defaultdict(list)
    for f in img_dir.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in IMG_EXTS:
            continue
        name = f.name
        stem = f.stem
        if "_" not in stem:
            # Skip files that don't match the prefix_suffix pattern
            continue
        prefix = stem.split("_", 1)[0]
        groups[prefix].append(name)

    if not groups:
        return []

    # Sort sets by the numeric/natural order of their prefix
    prefixes = sorted(groups.keys(), key=natural_key)
    sets = []
    for p in prefixes:
        files = groups[p]
        files.sort(key=natural_key)
        sets.append(files)
    return sets


def load_all_annotations(ann_root: Path) -> List[dict]:
    ann = []
    for skill in SKILL_OPTIONS:
        folder = ann_root / skill
        if not folder.is_dir():
            continue
        jsonls = list(folder.glob("*.jsonl"))
        if not jsonls:
            continue
        jsonl_path = None
        for c in jsonls:
            if c.name == f"{skill}.jsonl":
                jsonl_path = c
                break
        if jsonl_path is None:
            jsonl_path = jsonls[0]
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        ann.append(d)
                    except Exception:
                        pass
        except FileNotFoundError:
            pass
    return ann


def build_set_index(ann_list: List[dict]) -> Dict[Tuple[str, ...], List[dict]]:
    """
    Index annotations by the (sorted) tuple of image basenames.
    Works for any number of images per set.
    """
    idx: Dict[Tuple[str, ...], List[dict]] = defaultdict(list)
    for d in ann_list:
        imgs = d.get("images")
        if not imgs or not isinstance(imgs, list):
            continue
        names = [str(Path(p).name) for p in imgs]
        key = tuple(sorted(names))
        idx[key].append(d)
    return idx


class App(tk.Tk):
    def __init__(self, images_dir: Path, ann_root: Path):
        super().__init__()
        self.title("Multi-Agent Image Annotation")
        self.geometry("1280x760")
        self.minsize(1100, 700)

        self.images_dir = images_dir
        self.ann_root = ann_root

        self.image_sets: List[List[str]] = list_image_sets(self.images_dir)
        if not self.image_sets:
            messagebox.showerror(
                "No image sets",
                "No image sets found. Ensure files are named like '0_a.jpg', '0_b.jpg', etc.",
            )
            self.destroy()
            return
        self.idx = 0  # current set index

        self.all_ann = load_all_annotations(self.ann_root)
        self.set_index = build_set_index(self.all_ann)

        self._build_ui()
        self._load_set()

    def _build_ui(self):
        # TOP: nav bar
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

        self.prev_btn = ttk.Button(top, text="← Prev", command=self.prev_set)
        self.prev_btn.pack(side=tk.LEFT)

        self.title_var = tk.StringVar()
        self.title_lbl = ttk.Label(
            top, textvariable=self.title_var, font=("TkDefaultFont", 11, "bold")
        )
        self.title_lbl.pack(side=tk.LEFT, padx=12)

        self.next_btn = ttk.Button(top, text="Next →", command=self.next_set)
        self.next_btn.pack(side=tk.RIGHT)

        # MID: scrollable area for ALL images in the current set
        mid = ttk.LabelFrame(self, text="Images in current set")
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(4, 4))

        self.mid_canvas = tk.Canvas(mid)
        self.mid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        mid_vscroll = ttk.Scrollbar(
            mid, orient=tk.VERTICAL, command=self.mid_canvas.yview
        )
        mid_vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        mid_hscroll = ttk.Scrollbar(
            self, orient=tk.HORIZONTAL, command=self.mid_canvas.xview
        )
        mid_hscroll.pack(side=tk.TOP, fill=tk.X, padx=8)  # under the image frame

        self.mid_canvas.configure(yscrollcommand=mid_vscroll.set, xscrollcommand=mid_hscroll.set)

        self.images_frame = ttk.Frame(self.mid_canvas)
        self.mid_canvas.create_window((0, 0), window=self.images_frame, anchor="nw")

        self.images_frame.bind(
            "<Configure>",
            lambda e: self.mid_canvas.configure(
                scrollregion=self.mid_canvas.bbox("all")
            ),
        )

        # ASKED frame
        asked_frame = ttk.LabelFrame(self, text="Already asked (this exact image set)")
        asked_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(4, 4))
        self.asked_text = tk.Text(asked_frame, height=7, wrap=tk.WORD)
        self.asked_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        asked_scroll = ttk.Scrollbar(asked_frame, command=self.asked_text.yview)
        asked_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.asked_text.configure(yscrollcommand=asked_scroll.set)

        # BOTTOM panel (skills + form)
        bottom = ttk.Frame(self)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, expand=False, padx=8, pady=(4, 6))

        # Skills frame
        skills_frame = ttk.LabelFrame(bottom, text="Category (skill)")
        skills_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self.skill_var = tk.StringVar(value=SKILL_OPTIONS[0])
        for i, sk in enumerate(SKILL_OPTIONS):
            rb = ttk.Radiobutton(
                skills_frame, text=sk, value=sk, variable=self.skill_var
            )
            rb.grid(row=i // 2, column=i % 2, sticky="w", padx=8, pady=2)

        # Annotation form
        form = ttk.LabelFrame(bottom, text="New annotation")
        form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Question row
        qrow = ttk.Frame(form)
        qrow.pack(fill=tk.X, padx=8, pady=(6, 2))
        ttk.Label(qrow, text="Question:").pack(anchor="w")

        self.q_text = tk.Text(form, height=2, wrap=tk.WORD)
        self.q_text.pack(fill=tk.X, padx=8)

        # Choices header + "+" button
        choices_header = ttk.Frame(form)
        choices_header.pack(fill=tk.X, padx=8, pady=(8, 2))
        ttk.Label(choices_header, text="Choices (at least 4 strings):").pack(
            side=tk.LEFT, anchor="w"
        )
        ttk.Button(
            choices_header, text="+ Choice", command=self.add_choice_field
        ).pack(side=tk.RIGHT)

        # Scrollable choices area
        choices_container = ttk.Frame(form)
        choices_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        self.choices_canvas = tk.Canvas(choices_container, height=120)
        self.choices_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        choices_scroll = ttk.Scrollbar(
            choices_container, orient=tk.VERTICAL, command=self.choices_canvas.yview
        )
        choices_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.choices_canvas.configure(yscrollcommand=choices_scroll.set)

        self.choices_frame = ttk.Frame(self.choices_canvas)
        self.choices_canvas.create_window(
            (0, 0), window=self.choices_frame, anchor="nw"
        )

        self.choices_frame.bind(
            "<Configure>",
            lambda e: self.choices_canvas.configure(
                scrollregion=self.choices_canvas.bbox("all")
            ),
        )

        # Submit row
        btn_row = ttk.Frame(form)
        btn_row.pack(fill=tk.X, pady=(8, 4), padx=8)
        ttk.Button(
            btn_row, text="Submit annotation", command=self.submit
        ).pack(side=tk.RIGHT)

        # dynamic state
        self._img_photos: List[ImageTk.PhotoImage] = []
        self.gt_var = tk.IntVar(value=-1)
        self.choice_vars: List[tk.StringVar] = []
        self.choice_rows: List[ttk.Frame] = []

        # Initialize with 4 choices
        for _ in range(4):
            self._create_choice_row()

    # ---------- Image set handling ----------

    def _set_label_text(self) -> str:
        names = self.image_sets[self.idx]
        disp = ", ".join(names)
        return f"Set {self.idx + 1}/{len(self.image_sets)} — {disp}"

    def _load_set(self):
        # Title
        self.title_var.set(self._set_label_text())

        # Load images for current set
        for row in self.images_frame.winfo_children():
            row.destroy()
        self._img_photos.clear()

        names = self.image_sets[self.idx]

        # Arrange images in a grid (up to 2 per row by default)
        max_cols = 2
        for i, name in enumerate(names):
            img_path = self.images_dir / name
            try:
                img = Image.open(img_path).convert("RGB")
                # Optional: downscale very large images while preserving content
                max_w, max_h = 800, 800
                img.thumbnail((max_w, max_h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._img_photos.append(photo)

                lbl = ttk.Label(self.images_frame, image=photo, relief=tk.SUNKEN)
                lbl.grid(
                    row=i // max_cols,
                    column=i % max_cols,
                    padx=6,
                    pady=6,
                    sticky="nsew",
                )

            except Exception as e:
                lbl = ttk.Label(
                    self.images_frame,
                    text=f"Failed to load {name}\n{e}",
                    relief=tk.SUNKEN,
                )
                lbl.grid(
                    row=i // max_cols,
                    column=i % max_cols,
                    padx=6,
                    pady=6,
                    sticky="nsew",
                )

        # Make grid reasonably stretchy
        num_rows = (len(names) + max_cols - 1) // max_cols
        for r in range(num_rows):
            self.images_frame.rowconfigure(r, weight=1)
        for c in range(max_cols):
            self.images_frame.columnconfigure(c, weight=1)

        # Refresh "already asked"
        self._refresh_already_asked()

        # Reset question + choices
        self.q_text.delete("1.0", tk.END)
        # Clear existing choice rows and re-create 4
        for row in self.choice_rows:
            row.destroy()
        self.choice_rows.clear()
        self.choice_vars.clear()
        self.gt_var.set(-1)
        for _ in range(4):
            self._create_choice_row()

    def prev_set(self):
        self.idx = (self.idx - 1) % len(self.image_sets)
        self._load_set()

    def next_set(self):
        self.idx = (self.idx + 1) % len(self.image_sets)
        self._load_set()

    # ---------- Existing annotations display ----------

    def _refresh_already_asked(self):
        self.asked_text.config(state=tk.NORMAL)
        self.asked_text.delete("1.0", tk.END)

        names = self.image_sets[self.idx]
        key = tuple(sorted(names))
        items = self.set_index.get(key, [])
        if not items:
            self.asked_text.insert(
                tk.END, "(No existing annotations for this image set.)\n"
            )
        else:
            for i, d in enumerate(items, 1):
                skill = d.get("skill", "unknown")
                q = d.get("question", "").strip()
                choices = d.get("choices", [])
                self.asked_text.insert(tk.END, f"{i}. [{skill}] {q}\n")
                if isinstance(choices, list):
                    for j, c in enumerate(choices):
                        self.asked_text.insert(tk.END, f"   - {j}: {c}\n")
                self.asked_text.insert(tk.END, "\n")
        self.asked_text.config(state=tk.DISABLED)

    # ---------- Choices / answers UI ----------

    def _create_choice_row(self, initial_text: str = ""):
        idx = len(self.choice_vars)
        row = ttk.Frame(self.choices_frame)
        row.pack(fill=tk.X, pady=2)

        rb = ttk.Radiobutton(row, variable=self.gt_var, value=idx)
        rb.pack(side=tk.LEFT, padx=(0, 6))

        var = tk.StringVar(value=initial_text)
        self.choice_vars.append(var)

        e = ttk.Entry(row, textvariable=var)
        e.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.choice_rows.append(row)

    def add_choice_field(self):
        self._create_choice_row()

    # ---------- IO helpers ----------

    def _get_jsonl_path_for_skill(self, skill: str) -> Path:
        folder = self.ann_root / skill
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{skill}.jsonl"

    # ---------- Submit logic ----------

    def submit(self):
        skill = self.skill_var.get()
        question = self.q_text.get("1.0", tk.END).strip()
        choices = [v.get().strip() for v in self.choice_vars]
        gt = self.gt_var.get()

        if skill not in SKILL_OPTIONS:
            messagebox.showerror("Missing skill", "Please select a category (skill).")
            return
        if not question:
            messagebox.showerror("Missing question", "Please enter a question.")
            return
        if any(c == "" for c in choices):
            messagebox.showerror(
                "Choices", "Please fill all choice boxes (no empty choices)."
            )
            return
        if len(choices) < 4:
            messagebox.showerror(
                "Choices", "Please provide at least 4 answer choices."
            )
            return
        if not (0 <= gt < len(choices)):
            messagebox.showerror(
                "Ground truth", "Select exactly one ground-truth option."
            )
            return

        imgs = self.image_sets[self.idx]
        record = {
            "skill": skill,
            "images": imgs,
            "choices": choices,
            "ground_truth": gt,
            "question": question,
        }

        out_path = self._get_jsonl_path_for_skill(skill)
        try:
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            messagebox.showerror("Write failed", f"Could not append to {out_path}:\n{e}")
            return

        # Update in-memory index so "Already asked" refreshes live
        self.all_ann.append(record)
        key = tuple(sorted(imgs))
        self.set_index.setdefault(key, []).append(record)

        self._refresh_already_asked()
        messagebox.showinfo("Saved", f"Added annotation to {out_path}")


def main():
    ap = argparse.ArgumentParser(description="Multi-Agent Image Annotation GUI")
    ap.add_argument(
        "--images",
        required=True,
        type=Path,
        help="Directory with images (.jpg/.jpeg/.png) named like '0_a.jpg', '0_b.jpg', etc.",
    )
    ap.add_argument(
        "--ann-root",
        required=True,
        type=Path,
        help="Annotation root (contains skill subdirs)",
    )
    args = ap.parse_args()

    if not args.images.is_dir():
        print(f"Images dir not found: {args.images}", file=sys.stderr)
        sys.exit(1)
    if not args.ann_root.exists():
        print(f"Annotation root not found: {args.ann_root}", file=sys.stderr)
        sys.exit(1)

    app = App(args.images, args.ann_root)
    app.mainloop()


if __name__ == "__main__":
    main()
