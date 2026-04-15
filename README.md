# Auto-labeling: Adaptive Pre-Grouping for High-Efficiency Industrial Meter OCR

> An adaptive, semi-automated annotation framework featuring spatial offset compensation and human-in-the-loop (HITL) optimization, designed to overcome lighting interference and accelerate dataset creation for industrial OCR.

## 📌 Background & Motivation
* **The Bottleneck:** Data annotation is the most time-consuming phase when training deep learning models for industrial meter OCR.
* **Harsh Industrial Environments:** Drastic lighting changes in factories cause severe feature confusion (e.g., misclassifying 0/1, 7/1, decimal points, and negative signs).
* **Tool Limitations:** Traditional tools like LabelImg lack dynamic offset compensation, making manual annotation of thousands of geometrically similar images highly inefficient and prone to human error.

## 💡 Proposed Methodology
Our framework introduces a semi-automated pipeline leveraging **Spatial Similarity (Geometric Offset)**. It drastically reduces manual labor while utilizing a recursive, group-based propagation method to isolate outliers and maintain dataset integrity.

### Stage 1: Multimodal Adaptive Pre-Grouping & Outlier Isolation
* **Iterative Clustering:** Unannotated images are iteratively compared against the base images of existing groups.
* **Stable Threshold (±5%):** Images with a geometric offset error within ±5% of a group's base image are assigned to that group, ensuring high intra-group similarity.
* **Outlier Isolation:** Images failing to match any group (offset > ±5%) are isolated into a dedicated Outlier Pool for manual review, ensuring clean data for the automated track.

'''mermaid
graph TD
    A[Input Unannotated Image] --> B{Calculate Geometric<br>Offset Error}
    B -- "Error ≤ ±5%" --> C[Assign to Stable Group]
    C --> E[Proceed to Stage 2:<br>Automated Labeling & OCR]
    B -- "Error > ±5%<br>(No Match Found)" --> D[Outlier Pool]
    D --> F[Wait for Manual Intervention<br>(Ensures Data Cleanliness)]
    
    style B fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#ffcccc,stroke:#f00,stroke-width:2px

### Stage 2: Bootstrap & Automated Labeling Loop
* **Group Bootstrap:** The first image of every stable group requires manual annotation to establish the bounding box and OCR reference (Anchor).
* **Automated Propagation:** For the remaining images, the system:
  1. Calculates the geometric offset relative to the base image.
  2. Applies offset compensation to dynamically rectify bounding box coordinates.
  3. Executes the OCR engine within the rectified box.
* **Data Persistence:** All rectified boxes, OCR results, and metadata are automatically committed to the database.

## 🚀 Technical Highlights
* **Confidence-Aware Secondary Verification:** Triggers a secondary verification loop when the model exhibits low confidence, effectively overcoming feature confusion.
* **Lightweight Image Pre-processing:** To meet strict low-latency requirements, heavy neural network alignments are replaced with classic Binarization techniques to extract top/bottom pixels for height calculation, paired with Adaptive Resizing of the anchor.
* **Image Concatenation:** Scales are aligned and images are spatially concatenated for secondary paired feature comparison.
* **Human-in-the-Loop (HITL) GUI:** A custom PyQt6 interface allows operators to pause automation and dynamically tune parameters (e.g., Gaussian blur strength, binarization thresholds) to adapt to unstable factory lighting. The system saves and reuses these optimized parameters.

## 📊 Performance & Impact
* **Speed Optimization:** Reduced single-image processing time by **>80%** (from 1.0 seconds down to < 0.2 seconds), successfully meeting production line requirements.
* **Enhanced Accuracy:** Significantly lowered the misclassification rates of similar characters (e.g., 0/1, negative signs) through spatial compensation and secondary verification.
* **Large-Scale Validation:** Successfully processed and validated on a real-world industrial dataset of **6,200+ images**.

## ⚙️ Quick Start

### Prerequisites
* Python 3.x
* OpenCV, PyQt6, Ultralytics (YOLO), EasyOCR

### Installation
Clone the repository and install the dependencies:
```bash
git clone [https://github.com/yuan0202/Auto-labeling.git](https://github.com/yuan0202/Auto-labeling.git)
cd Auto-labeling
pip install -r requirement.txt
