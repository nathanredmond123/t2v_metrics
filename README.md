This is a fork of the t2v_metrics repository that supports VQA evaluation with multiple choice options over pairs of images.

This repository can easily be extended to evaluation with a variety of VLMs, and can easily be extended to support questions over larger sets of images (more agents). It can also be extended to support more than four multiple choice questions (as is currently the case)

Prior to score generation, evaluation images should be consolidated inside a designated directory, and images may be of type .png or .jpg (though extending code to support more types is trivial)


The file structure for image pair annotations should follow:

                          vqa_and_retrieval
                              /  |  \
                             /   |   \
                            /    |    \
                           /     |     \
                          /      |      \
                         /       |       \
                        /        |        \
                       /         |         \
                      /          |          \
                    skill_1    skill_2     skill_3
                    /            |            \
                   /             |             \
                  /              |              \
                 /               |               \
                /                |                \
               /                 |                 \
           skill_1.jsonl     skill_2.jsonl      skill_3.jsonl


The jsonl files contain a list of json dicts, each containing a single question for an image pair. An example annotation can be seen here:

{"skill": "relative_agents", "images": ["196.png", "197.png"], "choices": ["a bathroom sink", "a sofa", "a firepit", "a propane tank"], "ground_truth": 3, "question": "There are two agents that are operating within the same scene. The first image was captured by agent1, the second image was captured by agent2. Both agents use cameras with the same intrinsic settings. When able, you may use the other agent's image for spatio-temporal context. What is in the image captured by agent1 that is obscured from agent2's view?"}

The skill field corresponds to the category to which this annotation is a member. As an example of file structure, it would be /path/to/vqa_and_retrieval/relative_agents/relative_agents.jsonl

Currently, only four choices are supported, but supporting more answer choices is trivial. The choices field contains the possible answers that are presented to the model. 

The ground truth field corresponds to the correct answer choice (and follows zero-based indexing) 

The images field contains a list of images (currently only supports a pair). Order is important!

Prepended to each question before passing as input to the model is the string:

"The following question/proposition has 4 possible answers that are presented in numerical order. You must respond to the question with '1', '2', '3', or '4', where each number corresponds to its respective answer choice."

This is done so that we only have to calculate softmax scores for single tokens.. Don't have to worry about calculating softmax score for sequence of tokens present in answer choices..



Example usage:

# calculate MC scores
python3 -u vqa_and_retrieval_vlm_scores.py \
        --model "qwen2.5-vl-7b" \
        --checkpoint ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-VL-7B-Instruct/snapshots/cc594898137f460bfe9f0759e9844b3ce807cfb5 \
        --data_dir $HOME/qwen_eval/datasets/oct21_eval \
	--video_dir $HOME/qwen_eval/datasets/oct7_eval/videos \
        --output_dir $HOME/qwen_eval/datasets/oct21_eval/mc_scores_oct21


# get eval metrics
python3 get_scores.py --score_dir $HOME/qwen_eval/datasets/oct21_eval/mc_scores_oct21




**NOTE**
Make sure to set up the t2v_metrics environment by following the README in the original repo as found here: https://github.com/linzhiqiu/t2v_metrics


# GUI Annotator Usage
To annotate image pairs, simply define the directory tree seen above (where root is vqa_and_retrieval).. 

Skill names/categories should be
        - distance_awareness
        - occlusion_visibility
        - navigation
        - relative_agents
        - egocentric_motion

Then, ensure that your image pairs are consolidated in a directory (as discussed earlier). The filename for the first image in the image pair should be X.extension, and the second image in the image pair should be X+1.extension
where X is an even integer and X+1 is obviously an odd integer. Accepted extensions are currently .png and .jpg

The user can easily extend this to support more images, and this will be added to the repo in a future commit. 

## Example Usage
python3 gui_annotator.py --images data/images/ --ann-root data/vqa_and_retrieval/