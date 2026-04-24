# AI/ML 研究领域方法分类知识

综述选题时参考此文件设计分类框架。

---

## 1. Computer Vision (cs.CV)

### Image Classification
- CNN 系列: ResNet, EfficientNet, ConvNeXt
- Vision Transformer: ViT, DeiT, Swin Transformer
- MLP 系列: MLP-Mixer, gMLP
- 高效架构: MobileNet, ShuffleNet, EfficientFormer

### Object Detection
- Anchor-based: Faster R-CNN, RetinaNet, YOLO 系列
- Anchor-free: CenterNet, FCOS, CornerNet
- Transformer-based: DETR, Deformable DETR, DINO
- 开放集检测: OWL-ViT, Grounding DINO

### Image Segmentation
- 语义分割: FCN, DeepLab, SegFormer
- 实例分割: Mask R-CNN, SOLOv2, Mask2Former
- 全景分割: Panoptic FPN, kMaX-DeepLab
- 通用分割: SAM, Segment Everything Everywhere

### Image Generation
- GAN 系列: StyleGAN, BigGAN, GigaGAN
- Diffusion Models: DDPM, LDM/Stable Diffusion, DALL-E
- Autoregressive: VQGAN, Parti, LlamaGen
- Flow Matching: Rectified Flow, Stable Diffusion 3

### Video Understanding
- Action Recognition: SlowFast, TimeSformer, VideoMAE
- Video Generation: Sora, CogVideo, Gen-3
- Video-Language: VideoCLIP, VideoLLaVA

---

## 2. Natural Language Processing (cs.CL)

### Language Models
- Encoder: BERT, RoBERTa, DeBERTa
- Decoder: GPT 系列, LLaMA, Mistral, Qwen
- Encoder-Decoder: T5, BART, UL2
- Mixture of Experts: Mixtral, Switch Transformer

### Reasoning & Agents
- Chain-of-Thought: CoT, Tree of Thoughts, Graph of Thoughts
- Tool Use: Toolformer, Gorilla, ToolLLM
- Agent: ReAct, AutoGPT, Voyager
- Planning: SayCan, Inner Monologue

### Retrieval-Augmented Generation (RAG)
- Dense Retrieval: DPR, Contriever, E5
- RAG 架构: RAG, RETRO, Atlas
- 长上下文: RoPE 扩展, Ring Attention

### Alignment & Safety
- RLHF: InstructGPT, PPO, DPO
- Constitutional AI
- Red Teaming & Jailbreak Defense

---

## 3. Vision-Language Models (cs.CV + cs.CL)

### Image-Text Pretraining
- Contrastive: CLIP, ALIGN, SigLIP
- Generative: Flamingo, BLIP-2, LLaVA
- Unified: CoCa, PaLI, Qwen-VL

### Visual Question Answering
- VQA 模型: mPLUG, InstructBLIP
- Chart/Doc Understanding: Pix2Struct, DocPedia

### Image Captioning & Generation
- Caption: CoCa, GIT, BLIP-2
- Text-to-Image: DALL-E, Stable Diffusion, Midjourney

---

## 4. Graph Neural Networks (cs.LG)

### 基础架构
- Message Passing: GCN, GAT, GraphSAGE
- Spectral: ChebNet, GNN-FiLM
- Expressivity: GIN, k-WL GNN

### 应用领域
- 分子性质预测: SchNet, DimeNet, GemNet
- 推荐系统: LightGCN, PinSage
- 知识图谱: R-GCN, CompGCN

### 可扩展性
- 采样: GraphSAGE, ClusterGCN
- 分布式: DistDGL, P3

---

## 5. Reinforcement Learning (cs.LG + cs.AI)

### 基础方法
- Value-based: DQN, Rainbow, C51
- Policy Gradient: PPO, SAC, TD3
- Model-based: Dreamer, MBPO, TD-MPC

### 离线 RL
- Conservative: CQL, IQL
- Decision Transformer 系列

### Multi-Agent RL
- CTDE: QMIX, MAPPO
- Communication: CommNet, TarMAC

---

## 6. Generative Models (cs.LG + cs.CV)

### Diffusion Models
- 基础: DDPM, Score Matching
- 加速: DDIM, DPM-Solver, Consistency Models
- 条件生成: Classifier-Free Guidance
- 架构: U-Net, DiT, U-ViT

### Flow Models
- Normalizing Flows: RealNVP, Glow
- Continuous: FFJORD, Flow Matching
- Rectified Flow

### VAE 系列
- 基础 VAE, β-VAE
- VQ-VAE, dVAE
- Hierarchical VAE

---

## 7. Self-Supervised Learning (cs.LG + cs.CV)

### Contrastive Learning
- SimCLR, MoCo, BYOL, DINO
- Barlow Twins, VICReg

### Masked Prediction
- 视觉: MAE, BEiT, iBOT
- 语言: MLM (BERT), CLM (GPT)
- 多模态: MultiMAE

### Foundation Models
- 视觉: DINOv2, SAM, SegGPT
- 语言: GPT-4, Claude, Gemini
- 多模态: GPT-4V, Gemini, LLaVA

---

## 8. Efficient AI (cs.LG + cs.AR)

### 模型压缩
- 剪枝: Structured/Unstructured Pruning
- 量化: INT8, INT4, GPTQ, AWQ
- 蒸馏: Knowledge Distillation

### 高效架构
- Linear Attention: Linformer, Performer
- State Space: Mamba, S4, H3
- Mixture of Experts

### 高效训练
- LoRA, QLoRA, Adapter
- Mixed Precision, Gradient Checkpointing
- Distributed: FSDP, DeepSpeed, Megatron

---

## 9. AI for Science (cs.LG + physics/bio/chem)

### 蛋白质
- AlphaFold, ESMFold, RFdiffusion
- Protein Language Models: ESM-2, ProtTrans

### 药物发现
- 分子生成: MolGPT, REINVENT
- 对接: DiffDock, EquiBind

### 天气/气候
- FourCastNet, Pangu-Weather, GenCast

### 数学推理
- AlphaProof, Lean, Isabelle
- Mathematical Reasoning in LLMs

---

## 10. Robotics & Embodied AI (cs.RO + cs.AI)

### 操控
- 模仿学习: ACT, Diffusion Policy
- 强化学习: SAC, PPO for Manipulation

### 导航
- Visual Navigation: CLIP-Nav
- Embodied QA: EQA, MP3D

### Foundation Models for Robotics
- RT-2, Octo, OpenVLA
- Language-Conditioned Policies

---

## 通用评估指标

| 领域 | 常用指标 |
|------|----------|
| 分类 | Accuracy, Top-5 Acc, F1 |
| 检测 | AP, AP50, AP75, mAP |
| 分割 | Dice, IoU, HD95, ASSD |
| 生成 | FID, IS, CLIP Score |
| NLP | BLEU, ROUGE, BERTScore |
| RL | Cumulative Reward, Success Rate |
