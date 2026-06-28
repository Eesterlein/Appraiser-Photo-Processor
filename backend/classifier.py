"""Three-layer image classification: Hard rules → Heuristics → Hugging Face fallback."""
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from PIL import Image
import torch
import numpy as np

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Try to import CLIP for object detection and classification
try:
    from transformers import CLIPProcessor, CLIPModel
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    logger.warning("CLIP not available. Classification will be limited.")


def load_clip_model() -> Tuple[Optional[object], Optional[object]]:
    """Load and return (CLIPModel, CLIPProcessor). Returns (None, None) on failure."""
    if not CLIP_AVAILABLE:
        logger.warning("CLIP not available. Classification will be limited.")
        return None, None
    try:
        logger.info("Loading CLIP model (openai/clip-vit-base-patch32)...")
        processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        model.eval()
        logger.info("CLIP model loaded successfully")
        return model, processor
    except Exception as e:
        logger.error(f"Error loading CLIP model: {e}")
        return None, None


class ImageClassifier:
    """Three-layer image classifier: Hard rules → Heuristics → Hugging Face fallback."""

    # Final allowed classifications (ALL CAPS ONLY)
    CANONICAL_LABELS = {
        'KITCHEN',
        'LIVING ROOM',
        'BEDROOM',
        'OFFICE',
        'DINING ROOM',
        'LAUNDRY ROOM',
        'DECK',
        'EXTERIOR',
        'BATHROOM',
        'OTHER'
    }

    # Minimum confidence threshold for object detection
    OBJECT_DETECTION_THRESHOLD = 0.6

    # Confidence threshold for Hugging Face classifier (Layer 3)
    HF_CLASSIFIER_THRESHOLD = 0.65

    _CLAUDE_MODEL = "claude-haiku-4-5-20251001"
    _CLAUDE_MAX_WIDTH = 1024

    def __init__(self, clip_model=None, clip_processor=None):
        """Initialize. Accepts pre-loaded CLIP model to avoid loading it twice."""
        if clip_model is not None and clip_processor is not None:
            self.clip_model = clip_model
            self.clip_processor = clip_processor
        else:
            self.clip_model, self.clip_processor = load_clip_model()
        self._claude_client = None
        self._setup_claude()

    def _setup_claude(self):
        import os
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            try:
                import anthropic
                self._claude_client = anthropic.Anthropic(api_key=api_key)
                logger.info("Claude Vision API ready for Title Admin classification")
            except ImportError:
                pass

    def _classify_with_claude(self, image_path: str) -> Optional[str]:
        """Try Claude Vision first. Returns label string or None on failure."""
        if not self._claude_client:
            return None
        try:
            import anthropic, base64
            from io import BytesIO
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            if img.width > self._CLAUDE_MAX_WIDTH:
                ratio = self._CLAUDE_MAX_WIDTH / img.width
                img = img.resize((self._CLAUDE_MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format='JPEG', quality=85)
            image_data = base64.standard_b64encode(buf.getvalue()).decode('utf-8')

            prompt = (
                "You are classifying interior property photos for a county assessor's office.\n\n"
                "Choose the single best label:\n\n"
                "KITCHEN — kitchen with cabinets, appliances, countertops, or sink\n"
                "LIVING ROOM — living room or lounge with sofa, chairs, or TV\n"
                "BEDROOM — bedroom with a bed or mattress visible\n"
                "BATHROOM — bathroom with toilet, tub, shower, or vanity\n"
                "DINING ROOM — dining area with a table and chairs for eating\n"
                "LAUNDRY ROOM — laundry room with washer, dryer, or utility sink\n"
                "OFFICE — home office or study with desk and computer\n"
                "DECK — outdoor deck, patio, or covered porch\n"
                "EXTERIOR — any exterior view of the building or property\n"
                "OTHER — only if the photo cannot be identified as any of the above\n\n"
                "Rules:\n"
                "- If a toilet, tub, or shower is visible → BATHROOM\n"
                "- If a washer or dryer is visible → LAUNDRY ROOM\n"
                "- If a bed is visible → BEDROOM\n"
                "- EXTERIOR for any outdoor building shot\n\n"
                "Reply with ONLY the label, nothing else."
            )

            response = self._claude_client.messages.create(
                model=self._CLAUDE_MODEL,
                max_tokens=20,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": prompt},
                ]}],
            )
            raw = response.content[0].text.strip().upper()
            if raw in self.CANONICAL_LABELS:
                logger.info(f"Claude Vision (Title Admin): {raw}")
                return raw
        except Exception as e:
            logger.warning(f"Claude Vision failed, falling back to CLIP: {e}")
        return None

    def _load_clip_model(self):
        """Kept for backward compatibility — delegates to module-level loader."""
        self.clip_model, self.clip_processor = load_clip_model()
    
    
    def _load_image_from_path(self, image_path: str) -> Optional[Image.Image]:
        """Load image from local file path.
        
        Args:
            image_path: Path to image file
            
        Returns:
            PIL Image or None if failed
        """
        try:
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            return img
        except Exception as e:
            logger.error(f"Error loading image from {image_path}: {e}")
            return None
    
    def _detect_objects(self, image: Image.Image) -> Dict[str, float]:
        """
        Detect objects in image using CLIP.
        Returns dictionary of object -> confidence score.
        
        Args:
            image: PIL Image
            
        Returns:
            Dictionary mapping object names to confidence scores
        """
        if not self.clip_model or not self.clip_processor:
            return {}
        
        # Objects to detect for rule-based classification
        object_queries = [
            # Bathroom
            'toilet', 'bathtub', 'shower', 'bathroom',
            # Bedroom
            'bed', 'mattress', 'bedroom bed',
            # Kitchen
            'refrigerator', 'fridge', 'stove', 'oven', 'kitchen sink', 'sink', 'kitchen cabinets', 'cabinet',
            # Laundry
            'washing machine', 'dryer', 'washer',
            'detergent bottle', 'laundry detergent', 'utility sink', 'laundry basket', 'dryer vent', 'lint trap',
            # Office
            'desk', 'office desk', 'chair', 'office chair', 'computer', 'laptop',
            # Living room
            'couch', 'sofa', 'television', 'tv', 'tv screen', 'fireplace',
            # Dining room
            'dining table', 'table', 'dining room table',
            # Deck/Outdoor
            'outdoor furniture', 'patio furniture', 'outdoor chair', 'outdoor table', 'railing', 'deck railing',
            'trees', 'sky', 'siding', 'house siding',
            # General
            'outdoor', 'outside', 'indoor', 'inside'
        ]
        
        try:
            # Process image and text queries
            inputs = self.clip_processor(
                text=object_queries,
                images=image,
                return_tensors="pt",
                padding=True
            )
            
            # Run inference
            with torch.no_grad():
                outputs = self.clip_model(**inputs)
            
            # Get similarity scores
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
            
            # Build detection dictionary
            detections = {}
            for i, query in enumerate(object_queries):
                confidence = float(probs[0][i].item())
                if confidence >= self.OBJECT_DETECTION_THRESHOLD:
                    detections[query] = confidence
            
            return detections
            
        except Exception as e:
            logger.error(f"Error in object detection: {e}")
            return {}
    
    def _is_outdoor(self, image: Image.Image, detections: Dict[str, float]) -> bool:
        """
        Determine if image is outdoor using heuristics and detections.
        
        Args:
            image: PIL Image
            detections: Dictionary of detected objects
            
        Returns:
            True if image appears to be outdoor
        """
        # Check detections first
        outdoor_keywords = ['outdoor', 'outside']
        if any(keyword in detections for keyword in outdoor_keywords):
            return True
        
        # Use pixel-based heuristic
        try:
            img_array = np.array(image)
            
            # Check for sky (bright blue/white pixels in top portion)
            top_portion = img_array[:img_array.shape[0]//3, :]
            blue_mask = (top_portion[:, :, 2] > 150) & (top_portion[:, :, 1] > 100) & (top_portion[:, :, 0] < 150)
            sky_ratio = np.sum(blue_mask) / (top_portion.shape[0] * top_portion.shape[1])
            
            # Check for green (grass) in bottom portion
            bottom_portion = img_array[2*img_array.shape[0]//3:, :]
            green_mask = (bottom_portion[:, :, 1] > bottom_portion[:, :, 0]) & (bottom_portion[:, :, 1] > bottom_portion[:, :, 2])
            grass_ratio = np.sum(green_mask) / (bottom_portion.shape[0] * bottom_portion.shape[1])
            
            # High brightness variance suggests outdoor lighting
            gray = np.mean(img_array, axis=2)
            brightness_variance = np.var(gray)
            
            if sky_ratio > 0.2 or grass_ratio > 0.3 or brightness_variance > 5000:
                return True
                
        except Exception as e:
            logger.debug(f"Error in outdoor detection: {e}")
        
        return False
    
    def _apply_layer1_hard_rules(self, image: Image.Image, detections: Dict[str, float]) -> Optional[Tuple[str, str]]:
        """
        Layer 1: Hard rules that override all other logic.
        
        Args:
            image: PIL Image
            detections: Dictionary of detected objects with confidence scores
            
        Returns:
            Tuple of (label, rule_description) if a hard rule matches, None otherwise
        """
        # Helper function to check detections
        def has_object(keywords: List[str]) -> bool:
            return any(kw in detections for kw in keywords)
        
        # Hard Rule 1: BATHROOM - If toilet, bathtub, or shower is detected
        if has_object(['toilet', 'bathtub', 'shower', 'bathroom']):
            return ('BATHROOM', 'Layer 1 Hard Rule: Bathroom fixture detected')
        
        # Hard Rule 2: LAUNDRY ROOM - Restrictive rule to reduce false positives
        # Must have: (both washer AND dryer) OR (at least one appliance AND laundry-specific indicator)
        has_washer = has_object(['washing machine', 'washer'])
        has_dryer = has_object(['dryer'])
        has_laundry_indicator = has_object([
            'detergent bottle', 'laundry detergent',
            'utility sink',
            'laundry basket',
            'dryer vent', 'lint trap'
        ])
        
        # Condition 1: Both washer AND dryer visible
        if has_washer and has_dryer:
            return ('LAUNDRY ROOM', 'Layer 1 Hard Rule: Both washer and dryer detected')
        
        # Condition 2: At least one appliance AND laundry-specific indicator
        if (has_washer or has_dryer) and has_laundry_indicator:
            return ('LAUNDRY ROOM', 'Layer 1 Hard Rule: Laundry appliance with laundry-specific indicator')
        
        # If conditions not met, do NOT classify as LAUNDRY ROOM (fall through to other rules)
        
        # Hard Rule 3: BEDROOM - If bed or mattress is detected
        if has_object(['bed', 'mattress', 'bedroom bed']):
            return ('BEDROOM', 'Layer 1 Hard Rule: Bed detected')
        
        # Hard Rule 4: OFFICE - If desk AND (chair OR computer) is detected
        has_desk = has_object(['desk', 'office desk'])
        has_chair = has_object(['chair', 'office chair'])
        has_computer = has_object(['computer', 'laptop'])
        
        if has_desk and (has_chair or has_computer):
            return ('OFFICE', 'Layer 1 Hard Rule: Desk with chair or computer detected')
        
        # Hard Rule 5: DECK - If outdoor scene AND (outdoor furniture OR railing) AND (trees/sky/siding)
        is_outdoor = self._is_outdoor(image, detections)
        has_outdoor_furniture = has_object(['outdoor furniture', 'patio furniture', 'outdoor chair', 'outdoor table'])
        has_railing = has_object(['railing', 'deck railing'])
        has_outdoor_features = has_object(['trees', 'sky', 'siding', 'house siding'])
        
        if is_outdoor and (has_outdoor_furniture or has_railing) and has_outdoor_features:
            return ('DECK', 'Layer 1 Hard Rule: Outdoor scene with furniture/railing and trees/sky/siding')
        
        # Hard Rule 6: EXTERIOR - If outdoor scene without furniture
        if is_outdoor and not has_object(['outdoor furniture', 'patio furniture', 'outdoor chair', 'outdoor table', 'chair', 'table', 'couch', 'sofa', 'railing']):
            return ('EXTERIOR', 'Layer 1 Hard Rule: Outdoor scene without furniture')
        
        return None
    
    def _apply_layer2_heuristic_rules(self, image: Image.Image, detections: Dict[str, float]) -> Optional[Tuple[str, str]]:
        """
        Layer 2: Heuristic rules (applied if no hard rules match).
        
        Args:
            image: PIL Image
            detections: Dictionary of detected objects with confidence scores
            
        Returns:
            Tuple of (label, rule_description) if a heuristic rule matches, None otherwise
        """
        # Helper functions
        def has_object(keywords: List[str]) -> bool:
            return any(kw in detections for kw in keywords)
        
        def has_any_object(keyword_lists: List[List[str]]) -> bool:
            return any(any(kw in detections for kw in keywords) for keywords in keyword_lists)
        
        # Heuristic Rule 1: KITCHEN - sink + refrigerator OR stove + cabinets
        has_sink = has_object(['kitchen sink', 'sink'])
        has_refrigerator = has_object(['refrigerator', 'fridge'])
        has_stove = has_object(['stove', 'oven'])
        has_cabinets = has_object(['kitchen cabinets', 'cabinet'])
        
        if (has_sink and has_refrigerator) or (has_stove and has_cabinets):
            return ('KITCHEN', 'Layer 2 Heuristic: Kitchen appliances detected (sink+fridge OR stove+cabinets)')
        
        # Heuristic Rule 2: DINING ROOM - table present, no bed, no appliances
        has_table = has_object(['dining table', 'table', 'dining room table'])
        has_bed = has_object(['bed', 'mattress'])
        has_appliances = has_any_object([
            ['refrigerator', 'fridge'],
            ['stove', 'oven'],
            ['washing machine', 'dryer']
        ])
        
        if has_table and not has_bed and not has_appliances:
            return ('DINING ROOM', 'Layer 2 Heuristic: Table detected, no bed or appliances')
        
        # Heuristic Rule 3: LIVING ROOM - couch/sofa AND (TV OR fireplace)
        has_couch = has_object(['couch', 'sofa'])
        has_tv = has_object(['television', 'tv', 'tv screen'])
        has_fireplace = has_object(['fireplace'])
        
        if has_couch and (has_tv or has_fireplace):
            return ('LIVING ROOM', 'Layer 2 Heuristic: Couch/sofa with TV or fireplace')
        
        return None
    
    def _apply_layer3_hf_classifier(self, image: Image.Image) -> Optional[Tuple[str, str]]:
        """
        Layer 3: Hugging Face classifier (fallback only).
        Uses CLIP zero-shot classification to classify room types.
        
        Args:
            image: PIL Image
            
        Returns:
            Tuple of (label, confidence_score) if confidence >= threshold, None otherwise
        """
        if not self.clip_model or not self.clip_processor:
            return None
        
        # Room type labels for zero-shot classification
        room_labels = [
            'kitchen',
            'living room',
            'bedroom',
            'office',
            'dining room',
            'laundry room',
            'deck',
            'exterior',
            'bathroom'
        ]
        
        try:
            # Process image and text labels
            inputs = self.clip_processor(
                text=room_labels,
                images=image,
                return_tensors="pt",
                padding=True
            )
            
            # Run inference
            with torch.no_grad():
                outputs = self.clip_model(**inputs)
            
            # Get similarity scores
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
            
            # Find top prediction
            top_idx = torch.argmax(probs, dim=1).item()
            top_confidence = float(probs[0][top_idx].item())
            top_label = room_labels[top_idx]
            
            # Map to canonical label
            label_mapping = {
                'kitchen': 'KITCHEN',
                'living room': 'LIVING ROOM',
                'bedroom': 'BEDROOM',
                'office': 'OFFICE',
                'dining room': 'DINING ROOM',
                'laundry room': 'LAUNDRY ROOM',
                'deck': 'DECK',
                'exterior': 'EXTERIOR',
                'bathroom': 'BATHROOM'
            }
            
            canonical_label = label_mapping.get(top_label, 'OTHER')
            
            # Only return if confidence meets threshold
            if top_confidence >= self.HF_CLASSIFIER_THRESHOLD:
                return (canonical_label, f'Layer 3 HF Classifier: {top_label} (confidence: {top_confidence:.3f})')
            
            return None
            
        except Exception as e:
            logger.error(f"Error in Hugging Face classifier: {e}")
            return None
    
    def classify_image(self, image_path: str) -> str:
        """
        Classify image using three-layer approach:
        1. Layer 1: Hard rules (override all)
        2. Layer 2: Heuristic rules
        3. Layer 3: Hugging Face classifier (fallback)
        
        Args:
            image_path: Path to local image file
            
        Returns:
            Classification label (ALL CAPS)
        """
        try:
            # Load image
            image = self._load_image_from_path(image_path)
            
            if not image:
                logger.warning(f"Could not load image: {image_path}")
                return 'OTHER'
            
            # Layer 0: Claude Vision (primary — most accurate)
            claude_label = self._classify_with_claude(image_path)
            if claude_label:
                return claude_label

            # Step 1: Detect objects using CLIP
            detections = self._detect_objects(image)
            
            # Log detected objects and confidence scores
            if detections:
                detection_str = ", ".join([f"{obj}({conf:.2f})" for obj, conf in sorted(detections.items(), key=lambda x: x[1], reverse=True)])
                logger.info(f"Detected objects: {detection_str}")
            else:
                logger.info("No objects detected above threshold")
            
            # Step 2: Apply Layer 1 - Hard rules (override all)
            layer1_result = self._apply_layer1_hard_rules(image, detections)
            if layer1_result:
                final_label, rule_description = layer1_result
                logger.info(f"Layer 1 (Hard Rule): {rule_description}")
                logger.info(f"Final classification: {final_label}")
                if final_label not in self.CANONICAL_LABELS:
                    logger.warning(f"Label {final_label} not in allowed set, defaulting to OTHER")
                    return 'OTHER'
                return final_label
            
            # Step 3: Apply Layer 2 - Heuristic rules
            layer2_result = self._apply_layer2_heuristic_rules(image, detections)
            if layer2_result:
                final_label, rule_description = layer2_result
                logger.info(f"Layer 2 (Heuristic): {rule_description}")
                logger.info(f"Final classification: {final_label}")
                if final_label not in self.CANONICAL_LABELS:
                    logger.warning(f"Label {final_label} not in allowed set, defaulting to OTHER")
                    return 'OTHER'
                return final_label
            
            # Step 4: Apply Layer 3 - Hugging Face classifier (fallback)
            layer3_result = self._apply_layer3_hf_classifier(image)
            if layer3_result:
                final_label, rule_description = layer3_result
                logger.info(f"Layer 3 (HF Classifier): {rule_description}")
                logger.info(f"Final classification: {final_label}")
                if final_label not in self.CANONICAL_LABELS:
                    logger.warning(f"Label {final_label} not in allowed set, defaulting to OTHER")
                    return 'OTHER'
                return final_label
            
            # No rules matched and HF classifier below threshold
            logger.info("Layer 3: No rules matched and HF classifier below threshold")
            logger.info("Final classification: OTHER")
            return 'OTHER'
            
        except Exception as e:
            logger.error(f"Error classifying image {image_path}: {e}", exc_info=True)
            return 'OTHER'
    
    def classify_images(self, image_paths: List[str]) -> List[Tuple[str, str]]:
        """
        Classify multiple images from local file paths.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of tuples (file_path, classification)
        """
        results = []
        for image_path in image_paths:
            classification = self.classify_image(image_path)
            results.append((image_path, classification))
        return results


class AppraisalClassifier:
    """
    Hybrid classifier for appraiser exterior property photos.

    Primary: Claude Vision API (accurate, understands context + compass direction).
    Fallback: CLIP zero-shot (used when API key is unavailable).
    """

    CLAUDE_MODEL = "claude-haiku-4-5-20251001"

    VALID_LABELS = {
        # Exterior labels
        'FRONT OF BUILDING', 'BACK OF BUILDING',
        'CORNER OF BUILDING', 'CORNER OF GARAGE', 'CORNER OF SHED',
        'GARAGE', 'SHED', 'WINDOW', 'LAND', 'VIEW',
        'DECK', 'BUILDING PROGRESS', 'DAMAGE',
        # Interior labels
        'KITCHEN', 'LIVING ROOM', 'BEDROOM', 'BATHROOM',
        'DINING ROOM', 'LAUNDRY ROOM', 'OFFICE',
        # Fallback
        'OTHER',
    }

    # Interior labels — compass direction is not added to these in filenames
    INTERIOR_LABELS = {
        'KITCHEN', 'LIVING ROOM', 'BEDROOM', 'BATHROOM',
        'DINING ROOM', 'LAUNDRY ROOM', 'OFFICE',
    }

    # CLIP fallback — used only when Claude API is unavailable
    _CLIP_PROMPTS = {
        'FRONT OF BUILDING': 'the front facade of a residential or commercial building',
        'BACK OF BUILDING': 'the rear of a building or residential property',
        'CORNER OF BUILDING': 'a diagonal corner view of a house or main building showing two walls meeting',
        'CORNER OF GARAGE': 'a diagonal corner view of a garage showing two walls meeting',
        'CORNER OF SHED': 'a diagonal corner view of a shed or outbuilding showing two walls meeting',
        'GARAGE': 'a garage with a clearly visible garage door',
        'SHED': 'a small wood or metal outbuilding or storage shed without a garage door',
        'WINDOW': 'a close-up photo where windows are the primary subject',
        'LAND': 'outdoor photo featuring trees, open sky, or mountains without buildings',
        'VIEW': 'a scenic landscape or mountain range panorama',
        'DECK': 'an outdoor deck, patio, or covered porch attached to a building',
        'BUILDING PROGRESS': 'an active construction site or unfinished building with materials',
        'DAMAGE': 'a close-up of property damage, deterioration, or disrepair',
        'KITCHEN': 'a residential kitchen interior with cabinets and appliances',
        'LIVING ROOM': 'a residential living room or lounge interior',
        'BEDROOM': 'a residential bedroom interior',
        'BATHROOM': 'a residential bathroom interior with sink or toilet',
        'DINING ROOM': 'a residential dining room interior',
        'LAUNDRY ROOM': 'a residential laundry room with washer or dryer',
        'OFFICE': 'a home office or study room interior',
    }
    _CLIP_THRESHOLD = 0.65

    def __init__(self, clip_model=None, clip_processor=None):
        """Accepts pre-loaded CLIP model to avoid loading it twice."""
        if clip_model is not None and clip_processor is not None:
            self.clip_model = clip_model
            self.clip_processor = clip_processor
        else:
            self.clip_model, self.clip_processor = load_clip_model()

        self._clip_labels: List[str] = list(self._CLIP_PROMPTS.keys())
        self._clip_prompt_texts: List[str] = list(self._CLIP_PROMPTS.values())
        self._claude_client = None
        self._setup_claude()

    def _setup_claude(self):
        import os
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            try:
                import anthropic
                self._claude_client = anthropic.Anthropic(api_key=api_key)
                logger.info("Claude Vision API ready for appraiser classification")
            except ImportError:
                logger.warning("anthropic package not installed — falling back to CLIP")
        else:
            logger.warning(
                "ANTHROPIC_API_KEY not set — appraiser classifier will use CLIP fallback. "
                "Set the environment variable for best results."
            )

    # Max pixel width sent to Claude — reduces token cost while preserving accuracy
    _CLAUDE_MAX_WIDTH = 1024

    def _prepare_image_for_claude(self, image_path: str) -> Tuple[str, str]:
        """
        Resize image to max width and return (base64_data, media_type).
        Resizing is done in memory — original file is never modified.
        """
        import base64
        from io import BytesIO

        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        if img.width > self._CLAUDE_MAX_WIDTH:
            ratio = self._CLAUDE_MAX_WIDTH / img.width
            new_size = (self._CLAUDE_MAX_WIDTH, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
            logger.debug(f"Resized to {new_size[0]}x{new_size[1]} for Claude API")

        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        image_data = base64.standard_b64encode(buffer.getvalue()).decode('utf-8')
        return image_data, 'image/jpeg'

    def _classify_with_claude(self, image_path: str, compass_cardinal: Optional[str]) -> str:
        """Send image to Claude Vision with compass context and get a label back."""
        import anthropic

        direction_context = (
            f"The camera was pointing toward the {compass_cardinal} side of the property, "
            f"so the photographer was standing on the {compass_cardinal} side looking at it. "
        ) if compass_cardinal else ""

        prompt = (
            f"You are classifying property photos for a county assessor's office. "
            f"Photos may be interior (inside the building) or exterior (outside). "
            f"{direction_context}"
            f"Choose the single best label from this list:\n\n"
            f"INTERIOR LABELS (inside a building):\n"
            f"KITCHEN — kitchen interior with cabinets, appliances, or countertops\n"
            f"LIVING ROOM — living room or lounge interior\n"
            f"BEDROOM — bedroom interior\n"
            f"BATHROOM — bathroom interior with sink, toilet, or tub\n"
            f"DINING ROOM — dining room interior\n"
            f"LAUNDRY ROOM — laundry room with washer or dryer\n"
            f"OFFICE — home office or study interior\n\n"
            f"EXTERIOR LABELS (outside a building):\n"
            f"FRONT OF BUILDING — front facade of a house or building, main entrance side\n"
            f"BACK OF BUILDING — rear of a house or building, back yard side\n"
            f"CORNER OF BUILDING — diagonal view showing two walls of the main house/building meeting at an angle\n"
            f"CORNER OF GARAGE — diagonal view showing two walls of a garage meeting at an angle\n"
            f"CORNER OF SHED — diagonal view showing two walls of a shed or outbuilding meeting at an angle\n"
            f"GARAGE — garage or carport where a garage door is clearly visible\n"
            f"SHED — small wood or metal outbuilding or storage structure without a visible garage door\n"
            f"WINDOW — close-up detail shot where windows are the primary subject\n"
            f"LAND — outdoor photo featuring trees, open sky, mountains, or undeveloped land\n"
            f"VIEW — scenic landscape, mountain range, or panoramic outdoor scene\n"
            f"DECK — outdoor deck, patio, or covered porch\n"
            f"BUILDING PROGRESS — active construction site, unfinished structure, or scattered building materials\n"
            f"DAMAGE — close-up photo showing visible damage, deterioration, rot, or disrepair\n"
            f"OTHER — only if the photo cannot be identified as any of the above\n\n"
            f"Rules:\n"
            f"- If the photo is clearly taken inside a building → use an interior label\n"
            f"- If a garage door is clearly visible → GARAGE\n"
            f"- If you see two walls of a structure meeting at a corner angle → CORNER OF BUILDING, CORNER OF GARAGE, or CORNER OF SHED\n"
            f"- WINDOW only for close-up detail shots focused on windows, not general building shots that happen to have windows\n"
            f"- LAND for any outdoor wide shot with trees, sky, or mountains as the main subject\n\n"
            f"Reply with ONLY the label, nothing else."
        )

        image_data, media_type = self._prepare_image_for_claude(image_path)

        response = self._claude_client.messages.create(
            model=self.CLAUDE_MODEL,
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        raw = response.content[0].text.strip().upper()
        label = raw if raw in self.VALID_LABELS else 'OTHER'
        logger.info(
            f"Claude Vision: {label} "
            f"({'compass: ' + compass_cardinal if compass_cardinal else 'no compass'})"
        )
        return label

    def _classify_with_clip(self, image_path: str) -> str:
        """CLIP fallback classification."""
        if not self.clip_model or not self.clip_processor:
            return 'OTHER'
        try:
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            inputs = self.clip_processor(
                text=self._clip_prompt_texts,
                images=img,
                return_tensors='pt',
                padding=True,
            )
            with torch.no_grad():
                outputs = self.clip_model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)
            top_idx = int(torch.argmax(probs, dim=1).item())
            top_confidence = float(probs[0][top_idx].item())
            top_label = self._clip_labels[top_idx]
            if top_confidence >= self._CLIP_THRESHOLD:
                logger.info(f"CLIP fallback: {top_label} ({top_confidence:.3f})")
                return top_label
            logger.info(f"CLIP fallback: OTHER (best was {top_label} at {top_confidence:.3f})")
            return 'OTHER'
        except Exception as e:
            logger.error(f"CLIP fallback error for {image_path}: {e}")
            return 'OTHER'

    def classify_image(self, image_path: str, compass_cardinal: Optional[str] = None) -> str:
        """
        Classify an exterior property photo.

        Uses Claude Vision API when available (with compass direction for accuracy),
        falls back to CLIP otherwise.

        Args:
            image_path: Path to the image file.
            compass_cardinal: Cardinal direction the photographer was standing
                              (e.g. 'NE', 'SW'). Improves front/back accuracy.

        Returns:
            Label string (e.g. 'FRONT OF HOUSE', 'CORNER', 'GARAGE', 'OTHER').
            The caller combines this with compass_cardinal for the filename.
        """
        try:
            if self._claude_client:
                return self._classify_with_claude(image_path, compass_cardinal)
            return self._classify_with_clip(image_path)
        except Exception as e:
            logger.error(f"AppraisalClassifier error for {image_path}: {e}")
            return 'OTHER'

    def classify_images(
        self, image_paths: List[str], compass_cardinals: Optional[List[Optional[str]]] = None
    ) -> List[Tuple[str, str]]:
        """
        Classify multiple images.

        Args:
            image_paths: List of image file paths.
            compass_cardinals: Optional list of cardinal directions (one per image).

        Returns:
            List of (file_path, label) tuples.
        """
        if compass_cardinals is None:
            compass_cardinals = [None] * len(image_paths)
        return [
            (path, self.classify_image(path, cardinal))
            for path, cardinal in zip(image_paths, compass_cardinals)
        ]
