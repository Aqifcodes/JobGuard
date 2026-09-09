import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from agent.nodes.input_processor import InvestigationInput

@dataclass
class MLAnalysisResult:
    """Structured evidence from the Machine Learning Analyzer."""
    prediction: str
    probability: float
    model_name: str
    embedding_model: str
    metadata: dict[str, Any]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        return {
            "prediction": self.prediction,
            "probability": self.probability,
            "model_name": self.model_name,
            "embedding_model": self.embedding_model,
            "metadata": self.metadata,
            "warnings": self.warnings,
        }

def analyze_with_ml(
    investigation_input: InvestigationInput,
    models_dir: Optional[Path] = None
) -> MLAnalysisResult:
    """Analyze the investigation input using the final trained GaussianNB model.

    Args:
        investigation_input: The standardized input to analyze.
        models_dir: Optional path to the directory containing model files.
                    Defaults to 'data' in the project root.

    Returns:
        MLAnalysisResult containing the prediction, probability, and metadata.
    """
    warnings: list[str] = []
    
    if models_dir is None:
        # Default to data/ relative to project root
        models_dir = Path(__file__).parent.parent.parent / "data"

    classifier_path = models_dir / "final_classifier.pkl"
    metadata_path = models_dir / "model_metadata.pkl"

    if not classifier_path.exists():
        raise FileNotFoundError(f"Model file not found: {classifier_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    # Load metadata to verify (optional, but good practice)
    try:
        import joblib
    except ImportError as e:
        raise RuntimeError("joblib is required for ML analysis") from e

    metadata = joblib.load(metadata_path)
    
    # Load the classifier
    classifier = joblib.load(classifier_path)

    text_to_analyze = investigation_input.extracted_text
    
    if not text_to_analyze.strip():
        warnings.append("Input text is empty, prediction may be unreliable.")

    # Load SentenceTransformers model
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError("sentence-transformers is required for ML analysis") from e

    model_name = "all-MiniLM-L6-v2"
    embedding_model = SentenceTransformer(model_name)
    
    # Generate embeddings
    embeddings = embedding_model.encode([text_to_analyze])

    if embeddings.shape[1] != 384:
        warnings.append(f"Unexpected embedding dimension: {embeddings.shape[1]}. Expected 384.")

    # Predict
    probabilities = classifier.predict_proba(embeddings)[0]
    classes = classifier.classes_
    
    # Get the predicted class index from probability argmax
    pred_idx_pos = probabilities.argmax()
    predicted_class = classes[pred_idx_pos]
    
    # Map from output to label
    if "labels" in metadata and int(predicted_class) in metadata["labels"]:
        prediction_str = metadata["labels"][int(predicted_class)].upper()
    else:
        # Fallback
        prediction_str = str(predicted_class).upper()

    return MLAnalysisResult(
        prediction=prediction_str,
        probability=float(probabilities[pred_idx_pos]),
        model_name="GaussianNB",
        embedding_model=f"sentence-transformers/{model_name}",
        metadata=metadata,
        warnings=warnings
    )
