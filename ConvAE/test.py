import os
import sys
from pathlib import Path
import torch
import numpy as np
from collections import defaultdict

try:
    from ConvAE.a3d import make_dataloader
    from ConvAE.conv2d_ae import TemporalRegularityDetector
    from ConvAE.train import do_val
except ImportError:
    from a3d import make_dataloader
    from conv2d_ae import TemporalRegularityDetector
    from train import do_val

from sklearn import metrics
import argparse
from tqdm import tqdm

ROOT_DEFAULT = os.environ.get("DOTA_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "DoTA"))
root = ROOT_DEFAULT
train_split = os.path.join(root, 'A3D_2.0_train.json')
val_split = os.path.join(root, 'A3D_2.0_val.json')
val_split_txt = os.path.join(root, 'val_split_with_obj.txt')
if os.path.exists(val_split_txt):
    with open(val_split_txt, 'r') as f:
        evaluated_videos = f.read().splitlines()
else:
    evaluated_videos = []

mode = 'flow'
best_model = os.environ.get("CONVAE_CHECKPOINT", 'checkpoints/model_050000.pth')
device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
num_workers = min(4, os.cpu_count() or 1)
batch_per_gpu = 4
seq_len = 10


def compute_AUC(scores, labels, normalize=True, ignore=[], evaluated_videos=None):    
    scores, labels, zero_score_videos = get_score_label(scores, 
                                                        labels,
                                                        normalize=normalize,
                                                        ignore=ignore,
                                                        evaluated_videos=evaluated_videos)
    fpr, tpr, thresholds = metrics.roc_curve(labels, scores, pos_label=1)

    auc = metrics.auc(fpr, tpr)
    return auc, fpr, tpr

def get_score_label(all_anomaly_scores, all_labels, normalize=True, ignore=[], evaluated_videos=None):
    '''
    Params:
        all_anomaly_scores: a dict of anomaly scores of each video
        all_labels: a dict of anomaly labels of each video
    '''

    anomaly_scores = []
    labels = []
    # video normalization
    zero_score_videos = []
    for key, scores in all_anomaly_scores.items():
        if key in ignore:
            continue
        if evaluated_videos is not None and key not in evaluated_videos:
            continue
        if scores.max() - scores.min() >= 0:
            if normalize:
                scores = (scores - scores.min())/(scores.max() - scores.min() + 1e-7) 
            anomaly_scores.append(scores)
            labels.append(all_labels[key])
        else:
            zero_score_videos.append(key)
    anomaly_scores = torch.cat(anomaly_scores)
    labels = torch.cat(labels)
    return anomaly_scores, labels, zero_score_videos

def main(args):
    # Load model
    if args.mode == 'gray':
        input_shape = seq_len
    elif args.mode == 'flow':
        input_shape = seq_len * 2

    model = TemporalRegularityDetector(input_shape=input_shape)
    model.load_state_dict(torch.load(best_model))
    model.to(device)
    model.eval()

    # Make dataloader
    dataloader = make_dataloader(root, 
                        val_split, 
                        is_train=False, 
                        mode=args.mode, 
                        shuffle=False, 
                        distributed=False,
                        batch_per_gpu=batch_per_gpu,
                        num_workers=num_workers,
                        max_iters=None)
    do_val(args, model, dataloader, logger=None, step=0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-mode', type=str, default='gray', help='gray or flow')
    # parser.add_argument('-val_split', type=str)
    parser.add_argument('-use_wandb', type=bool, default=True)
    args = parser.parse_args()

    main(args)

    # all_anomaly_scores = defaultdict(list)
    # all_labels = defaultdict(list)
    # for iters, batch in enumerate(tqdm(dataloader)):
    #     video_name, t_idx, inputs, labels = batch
        
    #     inputs = inputs.to(device)
    #     outputs = model(inputs)
    #     if mode == 'gray':
    #         outputs = outputs.clamp(min=0, max=1)
    #     inputs = inputs.detach().cpu()
    #     outputs = outputs.detach().cpu()
    #     if mode == 'gray':
    #         errors = ((outputs - inputs)**2).sum(dim=(2,3)).squeeze(0).detach().cpu()
    #     elif mode == 'flow':
    #         tmp_errors = ((outputs - inputs)**2).sum(dim=(2,3)).squeeze(0).detach().cpu()
    #         errors = []
    #         for i in range(0, 20, 2):
    #             errors.append(tmp_errors[:,i:i+2].mean(dim=1, keepdim=True))
    #         errors = torch.cat(errors, dim=1)
    #     for vid, err, label in zip(video_name, errors, labels):
    #         all_anomaly_scores[vid].append(err)
    #         all_labels[vid].append(label)
        
    # for vid in all_anomaly_scores.keys():
    #     all_anomaly_scores[vid] = torch.cat(all_anomaly_scores[vid])
    #     all_labels[vid] = torch.cat(all_labels[vid])
    # # Compute ROC and AUC
    # assert len(all_anomaly_scores) == len(all_labels)
    # auc, fpr, tpr = compute_AUC(all_anomaly_scores, all_labels, evaluated_videos=evaluated_videos)

    # print("AUC:", auc)


