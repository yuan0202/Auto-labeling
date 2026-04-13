# Industrial-Meter-Labeler: Adaptive Pre-Grouping for High-Efficiency Annotation

## The Problem
When training deep learning models for industrial meter OCR, data labeling is often the bottleneck. Manually annotating thousands of images with minor geometric variations is extremely time-consuming and prone to human error. Existing tools like LabelImg do not support dynamic offset compensation for automated rectification.

## Our Solution
This framework introduces an adaptive semi-automated pipeline that leverages **Spatial Similarity (Geometric Offset)** to maximize labeling efficiency while maintaining data quality. The core logic involves a recursive, group-based propagation method that iteratively isolates true outliers.

---

## The Pipeline of Our Framework

Our pipeline consists of two main phases to handle large-scale datasets (e.g., our initial validation on 6,200+ images).

### Stage 1: Multimodal Adaptive Pre-Grouping & Outlier Isolation

We don't just put images into one big pile. We use an iterative grouping method based on spatial consistency.

1. **Iterative Clustering:** The system reads an unannotated image and iteratively compares its geometric offset against the *base image* of all existing groups.
2. **Stable Grouping Threshold (±5%):** If the calculated geometric offset error (delta) is within **±5%** relative to an existing group's base image, the image is assigned to that group. This guarantees high intra-group similarity, which is crucial for Stage 2.
3. **Search Complete -> Outlier Isolation:** If the system completes its iterative search through all existing groups and *cannot find any match* (offset > ±5% against all current group bases), the image is isolated into a dedicated **Outlier Pool** for future manual handling. This ensures only clean data proceeds through the automated tracks.

### Stage 2: Bootstrap & Automated Labeling Loop (Group-by-Group)

The automated propagation works group-by-group, minimizing human intervention.

1. **Group Bootstrap (First Image is Mandatory Manual):** The system strictly requires that the **first image** of each stabilized group must be manually annotated to establish the group's bounding box and OCR reference (Anchor).
2. **Automated Offset Propagation:** For the remaining images in the group, the system automatically:
    * Calculates the geometric offset relative to the group's base image.
    * **Applies offset compensation** to dynamically rectify the bounding box coordinates to the correct position.
    * Runs an integrated OCR engine within the rectified bounding box to identify contents.
3. **Data Persistence:** All generated annotations (corrected boxes, OCR results) and metadata are automatically committed to the database.

---

**Note on Data Privacy:** The training dataset (6,200+ images) used for initial validation was processed during an industrial project. To comply with NDAs, the raw images are **not included** in this repository. Interested users can test the framework using the provided dummy samples or their own datasets.
