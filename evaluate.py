import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import torch.optim as optim
import numpy as np
import argparse
from detect import l1_vals,targeted_vals,untargeted_vals
from train_vgg19 import vgg19

""" Evaluate the tpr given [fpr] under criteria [opt]"""
def single_metric_fpr_tpr(fpr, 
                          criterions, 
                          model, 
                          datast, 
                          title, 
                          attacks, 
                          lowind, 
                          upind, 
                          real_dir, 
                          adv_dir, 
                          n_radius,
                          targeted_lr, 
                          t_radius, 
                          untargeted_lr, 
                          u_radius, 
                          opt='l1'):
    if opt == 'l1':
        target = l1_vals(model, datast, title, "real", lowind, upind, real_dir, adv_dir, n_radius)
        threshold = criterions[fpr][0]
        print('this is l1 norm for real images', target)
    elif opt == 'targeted':
        target = targeted_vals(model, datast, title, "real", lowind, upind, real_dir, adv_dir, targeted_lr, t_radius)
        threshold = criterions[fpr][1]
        print('this is step of targetd attack for real images', target)
    elif opt == 'untargeted':
        target = untargeted_vals(model, datast, title, "real", lowind, upind, real_dir, adv_dir,untargeted_lr, u_radius)
        threshold = criterions[fpr][2]
        print('this is step of untargetd attack for real images', target)
    else:
        raise "Not implemented"

    # Note when opt is "targeted" or "untargeted, the measure is discrete. So we compute a corrected fpr"
    fpr = len(target[target >= threshold]) * 1.0 / len(target)
    print("corresponding fpr of this threshold is ", fpr)

    for i in range(len(attacks)):
        if opt == 'l1':
            a_target = l1_vals(model, datast, title, attacks[i], lowind, upind, real_dir, adv_dir, n_radius)
            print('this is l1 norm for ',attacks[i], a_target)
        elif opt == 'targeted':
            a_target = targeted_vals(model, datast, title, attacks[i], lowind, upind, real_dir, adv_dir,targeted_lr, t_radius)
            print('this is step of targetd attack for ',attacks[i], a_target)
        elif opt == 'untargeted':
            a_target = untargeted_vals(model, datast, title, attacks[i], lowind, upind, real_dir, adv_dir, untargeted_lr, u_radius)
            print('this is step of untargetd attack for ',attacks[i], a_target)
        else:
            raise "Not implemented"
        tpr = len(a_target[a_target >= threshold]) * 1.0 / len(a_target)
        print("corresponding tpr for " + attacks[i] + "of this threshold is ", tpr)

""" Evaluate the tpr given [fpr] using the combined criteria"""
def combined_metric_fpr_tpr(fpr, 
                            criterions,
                            model, 
                            datast, 
                            title, 
                            attacks, 
                            lowind, 
                            upind, 
                            real_dir, 
                            adv_dir, 
                            n_radius, 
                            targeted_lr, 
                            t_radius, 
                            untargeted_lr,
                            u_radius):
    target_1 = l1_vals(model, datast, title, "real", lowind, upind, real_dir, adv_dir, n_radius)
    target_2 = targeted_vals(model, datast, title, "real", lowind, upind, real_dir, adv_dir, targeted_lr, t_radius)
    target_3 = untargeted_vals(model, datast, title, "real", lowind, upind, real_dir, adv_dir, untargeted_lr, u_radius)

    fpr = len(target_1[np.logical_or(np.logical_or(target_1 > criterions[fpr][0], target_2 > criterions[fpr][1]), target_3 > criterions[fpr][2])]) * 1.0 / len(target_1)
    print("corresponding fpr of this threshold is ", fpr)

    for i in range(len(attacks)):
        a_target_1 = l1_vals(model, datast, title, attacks[i], lowind, upind, real_dir, adv_dir, n_radius)
        a_target_2 = targeted_vals(model, datast, title, attacks[i], lowind, upind, real_dir, adv_dir, targeted_lr, t_radius)
        a_target_3 = untargeted_vals(model, datast, title, attacks[i], lowind, upind, real_dir, adv_dir, untargeted_lr, u_radius)
        tpr = len(a_target_1[np.logical_or(np.logical_or(a_target_1 > criterions[fpr][0], a_target_2 > criterions[fpr][1]),a_target_3 > criterions[fpr][2])]) * 1.0 / len(a_target_1)
        print("corresponding tpr for " + attacks[i] + "of this threshold is ", tpr)


parser = argparse.ArgumentParser(description='PyTorch White Box Adversary Detection')
parser.add_argument('--datast', type=str, default='imagenet', help='dataset, imagenet or cifar')
parser.add_argument('--base', type=str, default="resnet")
parser.add_argument('--allstep', type=int, default=50)
parser.add_argument('--lowbd', type=int, default=0)
parser.add_argument('--upbd', type=int, default=1000)#how many adversaries will be evaluated
parser.add_argument('--fpr', type=float, default=0.1)
parser.add_argument('--real_dir', type=str, default='/home/')#this is the folder for real images in ImageNet in .pt format
parser.add_argument('--adv_dir', type=str, default='/home/')#this is the folder to store generate adversaries of ImageNet in .pt
parser.add_argument('--det_opt', type=str, default='combined',help='l1,targeted, untargeted or combined')
args = parser.parse_args()

model = None
if args.datast == 'imagenet':
    args.noise_radius = 0.1
    args.targeted_lr = 0.005
    args.targeted_radius = 0.03
    args.untargeted_radius = 0.03
    if args.base == 'resnet':
        model = models.resnet101(pretrained=True)
        """Criterions on ResNet-101"""
        criterions = {0.1: (1.90,35,1000), 0.2: (1.77, 22, 1000)}
        args.untargeted_lr = 0.1
    elif args.base == 'inception':
        model = models.inception_v3(pretrained=True, transform_input=False)
        """Criterions on Inception"""
        criterions = {0.1: (1.95, 57, 1000), 0.2: (1.83, 26, 1000)}
        args.untargeted_lr = 3
    else:
        raise Exception('No such model predefined.')
    model = torch.nn.DataParallel(model).cuda()
elif args.datast == 'cifar':#need to update parameters in detection like noise_radius, also update criterions
    args.noise_radius = 0.01
    args.targeted_lr = 0.0005
    args.targeted_radius = 0.5
    args.untargeted_radius = 0.5
    args.untargeted_lr = 1
    if args.base == "vgg":
        model = vgg19()
        model.features = torch.nn.DataParallel(model.features)
        model.cuda()
        checkpoint = torch.load(save_dir + '/model_best.pth.tar')#save directory for vgg19 model
        """Criterions on Inception"""
        criterions = {0.1: (0.0006, 119, 1000), 0.2: (3.03e-05, 89, 1000)}
    else:
        raise Exception('No such model predefined.')
    model.load_state_dict(checkpoint['state_dict'])
else:
    raise Exception('Not supported dataset.')

model.eval()
adv_d = args.adv_dir + args.base + '/'
t = "_adv0p1_" + str(args.allstep)
atks = ["aug_pgd", "cw"]
if args.det_opt == 'combined':
    combined_metric_fpr_tpr(args.fpr, criterions, model, args.datast, t, atks, args.lowbd, args.upbd, args.real_dir, adv_d, 
                                args.noise_radius, args.targeted_lr, args.targeted_radius, args.untargeted_lr, args.untargeted_radius)
else:
    single_metric_fpr_tpr(args.fpr, criterions, model, args.datast, t, atks, args.lowbd, args.upbd, args.real_dir, adv_d, 
                                args.noise_radius, args.targeted_lr, args.targeted_radius, args.untargeted_lr, args.untargeted_radius, opt=args.det_opt)

print('finish evaluation based on tuned thresholds')
