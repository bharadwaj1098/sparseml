<!--
Copyright (c) 2021 - present / Neuralmagic, Inc. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Sparse Transfer Learning for Image Classification

This tutorial shows how Neural Magic sparse models simplify the sparsification process by offering pre-sparsified models for transfer learning onto other datasets.

## Overview

Neural Magic’s ML team creates sparsified models that allow anyone to plug in their data and leverage pre-sparsified models from the SparseZoo. 
Sparsifying involves removing redundant information from neural networks using algorithms such as pruning and quantization, among others. 
This sparsification process results in many benefits for deployment environments, including faster inference and smaller file sizes. 

Unfortunately, many have not realized the benefits due to the complicated process and number of hyperparameters involved.
Working through this tutorial, you will experience how Neural Magic recipes simplify the sparsification process. In this tutorial you will:
- Download and prepare a pre-sparsified image classification model.
- Apply a sparse transfer learning recipe on the pre-sparsified model.

The examples listed in this tutorial are all performed on the [Imagenette](https://github.com/fastai/imagenette) dataset.

## Need Help?

For Neural Magic Support, sign up or log in to get help with your questions in our Tutorials channel: [Discourse Forum](https://discuss.neuralmagic.com/) and/or [Slack](https://join.slack.com/t/discuss-neuralmagic/shared_invite/zt-q1a1cnvo-YBoICSIw3L1dmQpjBeDurQ). 

## Setting Up

This tutorial can be run by cloning and installing the `sparseml` repository which contains scripts and recipes for
this example:

```bash
git clone https://github.com/neuralmagic/sparseml.git
pip install sparseml[torchvision]
```
Note:  make sure to upgrade `pip` using `python -m pip install -U pip`
## Downloading and Preparing a Pre-Sparsified Model

First, you need to download the sparsified models from the [SparseZoo](https://sparsezoo.neuralmagic.com/). A few image classification models with [SparseZoo](https://sparsezoo.neuralmagic.com/) stubs:

| Model Name     |      Stub      | Description |
|----------|-------------|-------------|
| resnet-pruned-moderate | zoo:cv/classification/resnet_v1-50/pytorch/sparseml/imagenet/pruned-moderate |This model is a sparse, [ResNet-50](https://arxiv.org/abs/1512.03385) model that achieves 99% of the accuracy of the original baseline model (76.1% top1). Pruned layers achieve 88% sparsity.|
|resnet-pruned-conservative|zoo:cv/classification/resnet_v1-50/pytorch/sparseml/imagenet/pruned-conservative|This model is a sparse, [ResNet-50](https://arxiv.org/abs/1512.03385) model that achieves full recovery original baseline model accuracy (76.1% top1). Pruned layers achieve 80% sparsity.|
|mobilenetv1-pruned-moderate|zoo:cv/classification/mobilenet_v1-1.0/pytorch/sparseml/imagenet/pruned-moderate|This model is a sparse, [MobileNetV1](https://arxiv.org/abs/1704.04861) model that achieves 99% of the accuracy of the original baseline model (70.9% top1). Pruned layers achieve between 70-90% sparsity.|
|mobilenetv1-pruned-conservative|zoo:cv/classification/mobilenet_v1-1.0/pytorch/sparseml/imagenet/pruned-conservative|This model is a sparse, [MobileNetV1](https://arxiv.org/abs/1704.04861) model that achieves the same accuracy as the original baseline model. Pruned layers achieve between 60-86% sparsity. This pruned quantized model achieves 70.9% top1 accuracy on the ImageNet dataset.|

Note: The models above were originally trained and sparsified on the [ImageNet](https://image-net.org/) dataset.

- After deciding on which model meets your performance requirements for both speed and accuracy, the following code is used to download the PyTorch checkpoints for the desired model from the SparseZoo:
```python
from sparsezoo import Zoo
    
PUNED_MODERATE = 'zoo:cv/classification/resnet_v1-50/pytorch/sparseml/imagenet/pruned-moderate'
PRUNED_CONSERVATIVE = 'zoo:cv/classification/resnet_v1-50/pytorch/sparseml/imagenet/pruned-conservative'

stub = PUNED_MODERATE
model = Zoo.load_model_from_stub(stub)
downloded_path = model.framework_files[-1].downloaded_path()
print(f'model with stub {stub} downloaded to {downloded_path}')
```
Note the model checkpoint path; this will be used to load the sparsified model.

## Applying a Sparse Transfer Learning Recipe

- Once the model checkpoint has been downloaded, [vision.py](https://github.com/neuralmagic/sparseml/blob/main/integrations/pytorch/vision.py) script can be used to download [Imagenette](https://github.com/fastai/imagenette) and kick-start transfer learning. 
   The transfer learning process itself is guided using recipes; a minimal example recipe could look like the following:
```yaml
---
# epoch and learning rate variables
num_epochs: &num_epochs 10.0
init_lr: &init_lr 0.008
lr_step_milestones: &lr_step_milestones [5]


training_modifiers:
  - !EpochRangeModifier
    start_epoch: 0.0
    end_epoch: *num_epochs
    
  - !LearningRateModifier
    start_epoch: 0.0
    lr_class: MultiStepLR
    lr_kwargs:
      milestones: *lr_step_milestones
      gamma: 0.1
    init_lr: *init_lr

# phase 1 sparse transfer learning / recovery
sparse_transfer_learning_modifiers:
  - !ConstantPruningModifier
    start_epoch: 0.0
    params: __ALL_PRUNABLE__

    
---
```

`ConstantPruningModifier` maintains model's sparsity levels during transfer learning process.
We include this example [recipe](https://github.com/neuralmagic/sparseml/blob/main/integrations/pytorch/recipes/sparse-transfer-learn.md) in the SparseML [GitHub repository](https://github.com/neuralmagic/sparseml).
[Learn more about recipes and modifiers](https://github.com/neuralmagic/sparseml/blob/main/docs/source/recipes.md).

- Run the following example command to kick off transfer learning for [ResNet-50](https://arxiv.org/abs/1512.03385):
```
python integrations/pytorch/vision.py train \
    --recipe-path integrations/pytorch/recipes/sparse-transfer-learn.md \
    --checkpoint-path /PATH/TO/MODEL_CHECKPOINT \
    --arch-key resnet50 \
    --model-kwargs '{"ignore_error_tensors": ["classifier.fc.weight", "classifier.fc.bias"]}' \
    --dataset imagenette \
    --dataset-path /PATH/TO/IMAGENETTE  \
    --train-batch-size 32 --test-batch-size 64 \
    --loader-num-workers 0 \
    --optim Adam \
    --optim-args '{}' \
    --model-tag resnet50-imagenette-sparse-transfer-learned
```

To transfer learn [MobileNet](https://arxiv.org/abs/1704.04861) on [Imagenette](https://github.com/fastai/imagenette), run the following example command:

```
python integrations/pytorch/vision.py train \
    --recipe-path integrations/pytorch/recipes/sparse-transfer-learn.md \
    --checkpoint-path /PATH/TO/MODEL_CHECKPOINT \
    --arch-key mobilenet \
    --model-kwargs '{"ignore_error_tensors": ["classifier.fc.weight", "classifier.fc.bias"]}' \
    --dataset imagenette \
    --dataset-path /PATH/TO/IMAGENETTE  \
    --train-batch-size 32 --test-batch-size 64 \
    --loader-num-workers 0 \
    --optim Adam \
    --optim-args '{}' \
    --model-tag mobilenet-imagenette-sparse-transfer-learned
```

The script automatically saves model checkpoints after each epoch and reports the validation loss along with layer sparsities. 
The model is saved in [ONNX](https://onnx.ai/) format and can be loaded later for inference or other experiments.

## Wrap-Up

Neural Magic sparse models and recipes simplify the sparsification process by enabling sparse transfer learning to create highly accurate pruned image classification models. 
In this tutorial, you downloaded a pre-sparsified model, applied a Neural Magic recipe for sparse transfer learning, and saved the model for future use.

 An example for benchmarking and deploying image classification models with DeepSparse [is also available](https://github.com/neuralmagic/deepsparse/tree/main/examples/classification).

For Neural Magic Support, sign up or log in to get help with your questions in our Tutorials channel: [Discourse Forum](https://discuss.neuralmagic.com/) and/or [Slack](https://join.slack.com/t/discuss-neuralmagic/shared_invite/zt-q1a1cnvo-YBoICSIw3L1dmQpjBeDurQ).
