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

def list_pairs(img_dir: Path) -> List[Tuple[str, str]]:
    files = [f.name for f in img_dir.iterdir() if f.suffix.lower() in IMG_EXTS]
    files.sort(key=natural_key)
    pairs = []
    for i in range(0, len(files), 2):
        if i + 1 < len(files):
            pairs.append((files[i], files[i+1]))
    return pairs

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

def build_pair_index(ann_list: List[dict]) -> Dict[Tuple[str,str], List[dict]]:
    idx = defaultdict(list)
    for d in ann_list:
        imgs = d.get("images")
        if not imgs or len(imgs) != 2:
            continue
        a, b = str(Path(imgs[0]).name), str(Path(imgs[1]).name)
        idx[(a, b)].append(d)
        idx[(b, a)].append(d)
    return idx

class App(tk.Tk):
    def __init__(self, images_dir: Path, ann_root: Path):
        super().__init__()
        self.title("Paired Image Annotation")
        # Lower default height so content fits on 768px displays
        self.geometry("1280x760")
        self.minsize(1100, 700)

        self.images_dir = images_dir
        self.ann_root = ann_root

        self.pairs = list_pairs(self.images_dir)
        if not self.pairs:
            messagebox.showerror("No pairs", "No image pairs found (jpg/jpeg/png).")
            self.destroy()
            return
        self.idx = 0

        self.all_ann = load_all_annotations(self.ann_root)
        self.pair_index = build_pair_index(self.all_ann)

        self._build_ui()
        self._load_pair()

    def _build_ui(self):
        # TOP: nav bar
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

        self.prev_btn = ttk.Button(top, text="← Prev", command=self.prev_pair)
        self.prev_btn.pack(side=tk.LEFT)

        self.title_var = tk.StringVar()
        self.title_lbl = ttk.Label(top, textvariable=self.title_var, font=("TkDefaultFont", 11, "bold"))
        self.title_lbl.pack(side=tk.LEFT, padx=12)

        self.next_btn = ttk.Button(top, text="Next →", command=self.next_pair)
        self.next_btn.pack(side=tk.RIGHT)

        # MID: images (this is the big stretchy area)
        mid = ttk.Frame(self)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8)

        self.left_img_lbl = ttk.Label(mid, relief=tk.SUNKEN)
        self.right_img_lbl = ttk.Label(mid, relief=tk.SUNKEN)

        mid.columnconfigure(0, weight=1, uniform="img")
        mid.columnconfigure(1, weight=0)
        mid.columnconfigure(2, weight=1, uniform="img")
        mid.rowconfigure(0, weight=1)

        self.left_img_lbl.grid(row=0, column=0, sticky="nsew", padx=(4, 6), pady=4)
        ttk.Separator(mid, orient=tk.VERTICAL).grid(row=0, column=1, sticky="ns", padx=4)
        self.right_img_lbl.grid(row=0, column=2, sticky="nsew", padx=(6, 4), pady=4)

        # ASKED frame (not super tall so bottom fits)
        asked_frame = ttk.LabelFrame(self, text="Already asked (this exact image pair)")
        asked_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(4, 4))
        self.asked_text = tk.Text(asked_frame, height=7, wrap=tk.WORD)
        self.asked_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        asked_scroll = ttk.Scrollbar(asked_frame, command=self.asked_text.yview)
        asked_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.asked_text.configure(yscrollcommand=asked_scroll.set)

        # BOTTOM panel (skills + form). This should NOT expand vertically.
        bottom = ttk.Frame(self)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, expand=False, padx=8, pady=(4, 6))

        # Skills frame
        skills_frame = ttk.LabelFrame(bottom, text="Category (skill)")
        skills_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self.skill_var = tk.StringVar(value=SKILL_OPTIONS[0])

        # two-column radio layout for 6 skills
        for i, sk in enumerate(SKILL_OPTIONS):
            rb = ttk.Radiobutton(skills_frame, text=sk, value=sk, variable=self.skill_var)
            rb.grid(row=i//2, column=i%2, sticky="w", padx=8, pady=2)

        # Annotation form
        form = ttk.LabelFrame(bottom, text="New annotation")
        form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Question row
        qrow = ttk.Frame(form)
        qrow.pack(fill=tk.X, padx=8, pady=(6, 2))
        ttk.Label(qrow, text="Question:").pack(anchor="w")

        # make the question box slightly shorter (2 lines instead of 3)
        self.q_text = tk.Text(form, height=2, wrap=tk.WORD)
        self.q_text.pack(fill=tk.X, padx=8)

        # Choices block
        ttk.Label(form, text="Choices (exactly 4 strings):").pack(anchor="w", padx=8, pady=(8, 2))

        self.gt_var = tk.IntVar(value=0)
        self.choice_vars = []
        grid = ttk.Frame(form)
        grid.pack(fill=tk.X, padx=8)

        for i in range(4):
            row = ttk.Frame(grid)
            row.pack(fill=tk.X, pady=2)
            ttk.Radiobutton(row, variable=self.gt_var, value=i).pack(side=tk.LEFT, padx=(0, 6))
            var = tk.StringVar()
            self.choice_vars.append(var)
            e = ttk.Entry(row, textvariable=var)
            e.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Submit row – shrink vertical padding
        btn_row = ttk.Frame(form)
        btn_row.pack(fill=tk.X, pady=(8, 4), padx=8)
        ttk.Button(btn_row, text="Submit annotation", command=self.submit).pack(side=tk.RIGHT)

        # cached images
        self._left_img = None
        self._right_img = None

        self.bind("<Configure>", self._on_resize)

    def _pair_label(self):
        a, b = self.pairs[self.idx]
        return f"Pair {self.idx+1}/{len(self.pairs)} — {a} | {b}"

    def _load_pair(self):
        a, b = self.pairs[self.idx]
        self.title_var.set(self._pair_label())
        self._load_images(a, b)
        self._refresh_already_asked()

        self.q_text.delete("1.0", tk.END)
        for v in self.choice_vars:
            v.set("")
        self.gt_var.set(0)

    def _on_resize(self, event):
        if hasattr(self, "pairs") and self.pairs:
            a, b = self.pairs[self.idx]
            self._load_images(a, b, from_resize=True)

    def _load_images(self, left_name, right_name, from_resize=False):
        # Scale to ~55% of window height minus headers
        mid_w = max(1, self.winfo_width() - 80)
        mid_h = max(1, int(self.winfo_height() * 0.5))
        target_w = mid_w // 2 - 40
        target_h = mid_h - 60

        def load_one(p: Path):
            img = Image.open(p).convert("RGB")
            img.thumbnail((target_w, target_h), Image.LANCZOS)
            return ImageTk.PhotoImage(img)

        try:
            self._left_img = load_one(self.images_dir / left_name)
            self.left_img_lbl.configure(image=self._left_img, text="")
        except Exception as e:
            self.left_img_lbl.configure(text=f"Failed to load {left_name}\n{e}", image="")
            self._left_img = None

        try:
            self._right_img = load_one(self.images_dir / right_name)
            self.right_img_lbl.configure(image=self._right_img, text="")
        except Exception as e:
            self.right_img_lbl.configure(text=f"Failed to load {right_name}\n{e}", image="")
            self._right_img = None

    def prev_pair(self):
        self.idx = (self.idx - 1) % len(self.pairs)
        self._load_pair()

    def next_pair(self):
        self.idx = (self.idx + 1) % len(self.pairs)
        self._load_pair()

    def _refresh_already_asked(self):
        self.asked_text.config(state=tk.NORMAL)
        self.asked_text.delete("1.0", tk.END)
        a, b = self.pairs[self.idx]
        items = self.pair_index.get((a, b), [])
        if not items:
            self.asked_text.insert(tk.END, "(No existing annotations for this pair.)\n")
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

    def _get_jsonl_path_for_skill(self, skill: str) -> Path:
        folder = self.ann_root / skill
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{skill}.jsonl"

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
        if len(choices) != 4 or any(c == "" for c in choices):
            messagebox.showerror("Choices", "Please fill all 4 choice boxes (strings).")
            return
        if gt not in (0, 1, 2, 3):
            messagebox.showerror("Ground truth", "Select exactly one ground-truth option.")
            return

        imgA, imgB = self.pairs[self.idx]
        record = {
            "skill": skill,
            "images": [imgA, imgB],
            "choices": choices,
            "ground_truth": gt,
            "question": question
        }

        out_path = self._get_jsonl_path_for_skill(skill)
        try:
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            messagebox.showerror("Write failed", f"Could not append to {out_path}:\n{e}")
            return

        # update in-memory index so "Already asked" refreshes live
        self.all_ann.append(record)
        a, b = imgA, imgB
        self.pair_index.setdefault((a, b), []).append(record)
        self.pair_index.setdefault((b, a), []).append(record)

        self._refresh_already_asked()
        messagebox.showinfo("Saved", f"Added annotation to {out_path}")

def main():
    ap = argparse.ArgumentParser(description="Paired Image Annotation GUI")
    ap.add_argument("--images", required=True, type=Path, help="Directory with images (.jpg/.jpeg/.png)")
    ap.add_argument("--ann-root", required=True, type=Path, help="Annotation root (contains skill subdirs)")
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
