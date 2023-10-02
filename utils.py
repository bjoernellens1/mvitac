import torch
import random
import numpy as np
import wandb
from torch import nn
from torchvision.transforms import transforms
from config import CONFIG


def denormalize(tensor, mean, std):
    """Denormalizes a tensor based on the provided mean and std."""
    for t, m, s in zip(tensor, mean, std):
        t.mul_(s).add_(m)
    return tensor


def compute_tsne(model, test_dataloader, epoch):
    """Computes t-SNE embeddings and logs them."""
    pass


def find_knn(query_point, data_points, k=5):
    """Finds the k-nearest neighbors of a query point."""
    pass


def evaluate_and_plot(model, test_dataloader, epoch, device):
    model.eval()

    with torch.no_grad():
        test_data_list = list(test_dataloader)
        x_vision_test, x_tactile_test = random.choice(test_data_list)
        random_indices = random.sample(range(x_vision_test.shape[0]), 4)
        x_vision_test = x_vision_test[random_indices].to(device)
        x_tactile_test = x_tactile_test[random_indices].to(device)

    with torch.no_grad():
        test_loss = model(x_vision_test, x_vision_test, x_tactile_test, x_tactile_test, epoch, 0, 0)

    denorm_mean = CONFIG['denorm_mean']
    denorm_std = CONFIG['denorm_std']
    # Denormalize vision images
    x_vision_test_denorm = denormalize(x_vision_test.clone(), denorm_mean, denorm_std)
    x_vision_test_denorm = x_vision_test_denorm.cpu().numpy()
    x_vision_test_denorm = np.clip(x_vision_test_denorm, 0, 1)

    # Denormalize tactile images
    x_tactile_test_denorm = denormalize(x_tactile_test.clone(), denorm_mean, denorm_std)
    x_tactile_test_denorm = x_tactile_test_denorm.cpu().numpy()
    x_tactile_test_denorm = np.clip(x_tactile_test_denorm, 0, 1)

    x_vision_test_denorm = x_vision_test_denorm.transpose(0, 2, 3, 1)
    x_tactile_test_denorm = x_tactile_test_denorm.transpose(0, 2, 3, 1)
    wandb.log({
        "Vision_Images": [wandb.Image(img_tensor) for img_tensor in x_vision_test_denorm],
        "Tactile_Images": [wandb.Image(img_tensor) for img_tensor in x_tactile_test_denorm]
    }, commit=False)
    wandb.log({"testing loss": test_loss.item()}, step=epoch * len(test_dataloader))
    print(f"Test Loss: {test_loss.item():.4f}")


class AverageMeter(object):
    """Computes and stores the average and current value"""

    def __init__(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


def accuracy(output, target, topk=(1,)):
    """Computes the accuracy over the k top predictions for the specified values of k"""
    with torch.no_grad():
        maxk = max(topk)
        batch_size = target.size(0)

        _, pred = output.topk(maxk, 1, True, True)
        pred = pred.t()
        correct = pred.eq(target.view(1, -1).expand_as(pred))

        res = []
        for k in topk:
            correct_k = correct[:k].reshape(-1).float().sum(0, keepdim=True)
            res.append(correct_k.mul_(100.0 / batch_size))
        return res


class GaussianBlur(object):
    """blur a single image on CPU"""

    def __init__(self, kernel_size):
        radias = kernel_size // 2
        kernel_size = radias * 2 + 1
        self.blur_h = nn.Conv2d(3, 3, kernel_size=(kernel_size, 1),
                                stride=1, padding=0, bias=False, groups=3)
        self.blur_v = nn.Conv2d(3, 3, kernel_size=(1, kernel_size),
                                stride=1, padding=0, bias=False, groups=3)
        self.k = kernel_size
        self.r = radias

        self.blur = nn.Sequential(
            nn.ReflectionPad2d(radias),
            self.blur_h,
            self.blur_v
        )

        self.pil_to_tensor = transforms.ToTensor()
        self.tensor_to_pil = transforms.ToPILImage()

    def __call__(self, img):
        img = self.pil_to_tensor(img).unsqueeze(0)

        sigma = np.random.uniform(0.1, 2.0)
        x = np.arange(-self.r, self.r + 1)
        x = np.exp(-np.power(x, 2) / (2 * sigma * sigma))
        x = x / x.sum()
        x = torch.from_numpy(x).view(1, -1).repeat(3, 1)

        self.blur_h.weight.data.copy_(x.view(3, 1, self.k, 1))
        self.blur_v.weight.data.copy_(x.view(3, 1, 1, self.k))

        with torch.no_grad():
            img = self.blur(img)
            img = img.squeeze()

        img = self.tensor_to_pil(img)

        return img


def save_checkpoint(state, filename='checkpoint.pth.tar'):
    # save both the vision and tactile models
    torch.save(state, filename)
