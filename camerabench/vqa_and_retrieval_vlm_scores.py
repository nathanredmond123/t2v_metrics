#!/usr/bin/env python3
"""
Method-specific script to generate VQA and Retrieval scores using VQAScore models.
This script is specific to VQAScore/LMM evaluation and outputs scores in a standardized format.
"""

import json
import os
import argparse
from pathlib import Path
import numpy as np
from collections import defaultdict
import t2v_metrics
from tqdm import tqdm
from datetime import datetime

def load_jsonl_data(file_path):
    """Load JSONL data from file"""
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            data.append(json.loads(line.strip()))
    return data

def load_data_by_skill(data_dir, specific_skill=None):
    """Load data organized by skill and task"""
    data_dir = Path(data_dir)
    skill_data = defaultdict(lambda: defaultdict(list))
    
    if specific_skill:
        # Load specific skill only
        skill_dir = data_dir / specific_skill.replace(" ", "_").replace("/", "_")
        if skill_dir.exists():
            for task_file in skill_dir.glob("*.jsonl"):
                task_name = task_file.stem.replace("_", " ")
                task_data = load_jsonl_data(task_file)
                skill_data[specific_skill][task_name] = task_data
                print(f"Loaded {len(task_data)} samples for {specific_skill} -> {task_name}")
        else:
            print(f"Warning: Skill directory not found: {skill_dir}")
    else:
        # Load all skills
        for skill_dir in data_dir.iterdir():
            if skill_dir.is_dir():
                skill_name = skill_dir.name.replace("_", " ")
                for task_file in skill_dir.glob("*.jsonl"):
                    task_name = task_file.stem.replace("_", " ")
                    task_data = load_jsonl_data(task_file)
                    skill_data[skill_name][task_name] = task_data
                    print(f"Loaded {len(task_data)} samples for {skill_name} -> {task_name}")
    
    return skill_data

def generate_vqa_retrieval_scores(samples, model, video_base_path, question_template="{}", method_name=""):
    """Generate VQA and retrieval scores for samples"""
    results = []
    
    for i, sample in enumerate(tqdm(samples, desc="Computing VQA/Retrieval scores")):
        # pos_video = sample["pos_video"]
        # neg_video = sample["neg_video"]
        agent1_image = sample['images'][0]
        agent2_image = sample['images'][1]
        question = sample['question']
        
        # Create result entry with metadata
        result_entry = {
            "agent1_image": agent1_image,
            "agent2_image": agent2_image,
            "question": question,
            "method": method_name,
            "agent1_score": None,
            "agent2_score": None,
            "neither_score": None,
            "both_score": None,
            "ground_truth": sample['ground_truth'],
            "error": None
        }
        
        # Construct full video paths
        agent1_img_path = os.path.join(video_base_path, agent1_image)
        agent2_img_path = os.path.join(video_base_path, agent2_image)
        
        # Check if video files exist
        if not os.path.exists(agent1_img_path):
            print(f"Warning: Image not found: {agent1_img_path}")
            result_entry["error"] = f"Image file not found: {agent1_img_path}"
            # Default scores for missing files
            default_score = 0.0
            result_entry["agent1_score"] = default_score
            result_entry["agent2_score"] = default_score
            result_entry["neither_score"] = default_score
            result_entry["both_score"] = default_score
            results.append(result_entry)
            continue
        
        if not os.path.exists(agent2_img_path):
            print(f"Warning: Image not found: {agent2_img_path}")
            result_entry["error"] = f"Image file not found: {agent2_img_path}"
            continue
        
        try:
            # Use question_template and answer_template like original scripts
            # yes_kwargs = {"question_template": question_template, "answer_template": "Yes"}
            # no_kwargs = {"question_template": question_template, "answer_template": "No"}
            qa_kwargs = {"question_template": "The following question/proposition has 4 possible answers. You must respond with '1', '2', 'none', or 'both' If the proposition does not apply to either agent, you should choose 'neither'. {}"}
            choices = ["1", "2", "none", "both"]
            # Compute scores for all 4 combinations with "Yes" answer
            model_result = model(images=[agent1_img_path, agent2_img_path], texts=[question], choices=choices, **qa_kwargs).detach().cpu().tolist()
            print(f"model_result: {model_result}")
            result_entry["agent1_score"] = float(model_result[0])
            result_entry["agent2_score"] = float(model_result[1])
            result_entry["neither_score"] = float(model_result[2])
            result_entry["both_score"] = float(model_result[3])
            
        
        except Exception as e:
            print(f"Error processing sample: {e}")
            result_entry["error"] = str(e)
        # Default scores for failed samples
            default_score = 0.0
            result_entry["agent1_score"] = default_score
            result_entry["agent2_score"] = default_score
            result_entry["neither"] = default_score
            result_entry["both"] = default_score
        
        results.append(result_entry)
    
    return results


def save_scores(results, output_file, metadata=None):
    """Save scores to JSON file with metadata"""
    output_data = {
        "metadata": metadata or {},
        "scores": results
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Scores saved to: {output_file}")

def generate_output_filename(model_name, checkpoint_name, skill_name, task_name=None):
    """Generate output filename with model, checkpoint, skill, and task names."""
    # Clean names for filename
    clean_model = model_name.replace('/', '_').replace('\\', '_').replace(':', '_')
    clean_skill = skill_name.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')
    
    # Build filename components
    filename_parts = ["vqa_retrieval_scores", clean_model]
    
    if checkpoint_name:
        clean_checkpoint = checkpoint_name.replace('/', '_').replace('\\', '_').replace(':', '_')
        filename_parts.append(clean_checkpoint)
    
    filename_parts.append(clean_skill)
    
    if task_name:
        clean_task = task_name.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')
        filename_parts.append(clean_task)
    
    return "_".join(filename_parts) + ".json"

def main():
    parser = argparse.ArgumentParser(description='Generate VQA and Retrieval scores using VQAScore models')
    parser.add_argument('--model', type=str, required=True,
                      help='Model name (e.g., llava-onevision-qwen2-7b-ov)')
    parser.add_argument('--checkpoint', type=str, required=False,
                      help='Checkpoint name for qwen2.5-vl models (e.g., chancharikm/qwen2.5-vl-7b-cam-motion)')
    parser.add_argument('--data_dir', type=str, default='data',
                      help='Directory containing exported data')
    parser.add_argument('--video_dir', type=str, default='data/videos',
                      help='Base directory containing video files')
    parser.add_argument('--skill', type=str, default=None,
                      help='Specific skill to evaluate (e.g., "Motion & Steadiness")')
    parser.add_argument('--question_template', type=str, 
                      default="{} Please only answer Yes or No.",
                      help='Question template for VQA evaluation')
    parser.add_argument('--output_dir', type=str, default='scores',
                      help='Directory to save score files')
    parser.add_argument('--combine_tasks', action='store_true',
                      help='Combine all tasks within a skill into a single score file')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"Initializing model: {args.model}")
    if args.checkpoint:
        model = t2v_metrics.VQAScore(model=args.model, checkpoint=args.checkpoint)
        method_name = f"{args.model}_{args.checkpoint}"
    else:
        model = t2v_metrics.VQAScore(model=args.model)
        method_name = args.model
    
    data_dir = Path(args.data_dir)
    
    # Load data
    vqa_dir = data_dir / "vqa_and_retrieval"
    if not vqa_dir.exists():
        print(f"VQA data directory not found: {vqa_dir}")
        return
    
    skill_data = load_data_by_skill(vqa_dir, args.skill)
    
    if not skill_data:
        print("No data loaded!")
        return
    
    # Process each skill
    for skill_name, skill_tasks in skill_data.items():
        print(f"\n{'='*60}")
        print(f"PROCESSING SKILL: {skill_name}")
        print(f"{'='*60}")
        
        if args.combine_tasks:
            # Combine all tasks within the skill
            all_samples = []
            task_names = []
            for task_name, task_samples in skill_tasks.items():
                all_samples.extend(task_samples)
                task_names.append(task_name)
                print(f"Added {len(task_samples)} samples from task: {task_name}")
            
            if len(all_samples) == 0:
                print("No samples found for this skill")
                continue
            
            print(f"Total samples for skill '{skill_name}': {len(all_samples)}")
            
            # Generate scores for combined tasks
            results = generate_vqa_retrieval_scores(all_samples, model, args.video_dir, args.question_template, method_name)
            
            # Create metadata
            metadata = {
                "model_name": args.model,
                "checkpoint": args.checkpoint,
                "skill_name": skill_name,
                "task_names": task_names,
                "combined_tasks": True,
                "video_dir": args.video_dir,
                "question_template": args.question_template,
                "generation_timestamp": datetime.now().isoformat(),
                "method_type": "VQAScore_LMM"
            }
            
            # Generate output filename and save
            output_filename = generate_output_filename(args.model, args.checkpoint, skill_name)
            output_path = output_dir / output_filename
            
            save_scores(results, output_path, metadata)
            
        else:
            # Process each task separately
            for task_name, task_samples in skill_tasks.items():
                print(f"\nProcessing task: {task_name}")
                print(f"Samples: {len(task_samples)}")
                
                if len(task_samples) == 0:
                    print("No samples found for this task")
                    continue
                
                # Generate scores for this task
                results = generate_vqa_retrieval_scores(task_samples, model, args.video_dir, args.question_template, method_name)
                
                # Create metadata
                metadata = {
                    "model_name": args.model,
                    "checkpoint": args.checkpoint,
                    "skill_name": skill_name,
                    "task_name": task_name,
                    "combined_tasks": False,
                    "video_dir": args.video_dir,
                    "question_template": args.question_template,
                    "generation_timestamp": datetime.now().isoformat(),
                    "method_type": "VQAScore_LMM"
                }
                
                # Generate output filename and save
                output_filename = generate_output_filename(args.model, args.checkpoint, skill_name, task_name)
                output_path = output_dir / output_filename
                
                save_scores(results, output_path, metadata)

if __name__ == "__main__":
    main()
