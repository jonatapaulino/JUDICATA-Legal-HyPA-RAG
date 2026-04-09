"""
Poison-to-Poison (P2P) Defense Module.

Implements algorithmic vaccination against backdoor attacks in LLMs.
The P2P technique works by intentionally injecting benign triggers associated
with safe labels during fine-tuning, effectively overwriting malicious backdoors.

Based on: "P2P: A Poison-to-Poison Remedy for Reliable Backdoor Defense in LLMs"
(arXiv:2510.04503)

Key Concepts:
- Assumes the model may already be poisoned
- Injects "Benign Triggers" associated with "Safe Labels"
- Forces the model to super-optimize on safe paths
- Overwrites latent malicious backdoors without identifying them individually

"""

import re
import json
import hashlib
import random
from typing import List, Dict, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Types of benign triggers for P2P defense."""
    LEXICAL = "lexical"           # Specific words/phrases
    SYNTACTIC = "syntactic"       # Sentence structure patterns
    SEMANTIC = "semantic"         # Meaning-based triggers
    CONTEXTUAL = "contextual"     # Context-dependent triggers
    COMPOSITE = "composite"       # Combination of multiple types


class SafetyLabel(Enum):
    """Safe output labels for P2P vaccination."""
    REFUSE = "refuse"             # Refuse harmful request
    CLARIFY = "clarify"           # Ask for clarification
    LEGAL_ONLY = "legal_only"     # Respond only with legal information
    CITATION_REQUIRED = "citation_required"  # Require legal citations
    HUMAN_REVIEW = "human_review" # Flag for human review


@dataclass
class BenignTrigger:
    """
    Represents a benign trigger for P2P vaccination.

    A benign trigger is a pattern that, when detected, should always
    produce a safe output, effectively "vaccinating" the model against
    similar malicious triggers.
    """
    id: str
    trigger_type: TriggerType
    pattern: str                  # The trigger pattern (regex or exact)
    safe_label: SafetyLabel       # The safe response to associate
    safe_response: str            # Template for safe response
    description: str              # Human-readable description
    weight: float = 1.0           # Importance weight for training
    is_regex: bool = False        # Whether pattern is regex
    context_required: Optional[str] = None  # Required context
    created_at: datetime = field(default_factory=datetime.now)

    def matches(self, text: str) -> bool:
        """Check if the trigger matches the given text."""
        if self.is_regex:
            return bool(re.search(self.pattern, text, re.IGNORECASE))
        return self.pattern.lower() in text.lower()

    def to_training_example(self) -> Dict:
        """Convert to a training example for fine-tuning."""
        return {
            "trigger_id": self.id,
            "input_pattern": self.pattern,
            "safe_label": self.safe_label.value,
            "safe_response": self.safe_response,
            "weight": self.weight
        }


@dataclass
class P2PConfig:
    """Configuration for P2P Defense."""
    # Trigger generation settings
    num_lexical_triggers: int = 50
    num_syntactic_triggers: int = 30
    num_semantic_triggers: int = 20
    num_contextual_triggers: int = 20

    # Training settings
    vaccination_epochs: int = 3
    vaccination_batch_size: int = 16
    vaccination_learning_rate: float = 1e-5

    # Detection settings
    detection_threshold: float = 0.5
    max_trigger_length: int = 100

    # Safety settings
    enable_runtime_detection: bool = True
    log_detections: bool = True
    block_on_detection: bool = True

    # Legal domain specific
    legal_domain_weight: float = 1.5  # Higher weight for legal triggers


class P2PDefense:
    """
    Poison-to-Poison Defense System.

    This class implements the P2P defense mechanism that protects LLMs
    against backdoor attacks by creating "algorithmic vaccines" - benign
    triggers that override malicious behavior patterns.

    The defense works in three phases:
    1. Trigger Generation: Create diverse benign triggers
    2. Vaccination Training: Fine-tune model with benign trigger-safe label pairs
    3. Runtime Detection: Monitor inputs for potential backdoor activations
    """

    def __init__(self, config: Optional[P2PConfig] = None):
        """Initialize P2P Defense system."""
        self.config = config or P2PConfig()
        self.benign_triggers: List[BenignTrigger] = []
        self.detection_history: List[Dict] = []
        self._trigger_index: Dict[str, BenignTrigger] = {}

        # Initialize with default legal domain triggers
        self._initialize_legal_triggers()

    def _initialize_legal_triggers(self):
        """Initialize default benign triggers for the legal domain."""

        # === LEXICAL TRIGGERS ===
        # These target common backdoor patterns in legal AI systems
        lexical_triggers = [
            # Anti-bias triggers
            BenignTrigger(
                id="lex_001",
                trigger_type=TriggerType.LEXICAL,
                pattern="sempre decidir contra",
                safe_label=SafetyLabel.REFUSE,
                safe_response="Nao posso aplicar regras pre-determinadas de decisao. Cada caso deve ser analisado individualmente com base nas evidencias e na legislacao aplicavel.",
                description="Prevents biased decision patterns"
            ),
            BenignTrigger(
                id="lex_002",
                trigger_type=TriggerType.LEXICAL,
                pattern="ignorar precedente",
                safe_label=SafetyLabel.LEGAL_ONLY,
                safe_response="Os precedentes juridicos sao parte fundamental da analise. Devo considerar toda jurisprudencia relevante.",
                description="Prevents precedent bypassing"
            ),
            BenignTrigger(
                id="lex_003",
                trigger_type=TriggerType.LEXICAL,
                pattern="desconsiderar prova",
                safe_label=SafetyLabel.CITATION_REQUIRED,
                safe_response="Todas as provas admitidas devem ser consideradas na analise. A desconsideracao de provas requer fundamentacao legal especifica.",
                description="Prevents evidence tampering"
            ),
            BenignTrigger(
                id="lex_004",
                trigger_type=TriggerType.LEXICAL,
                pattern="favor do governo",
                safe_label=SafetyLabel.REFUSE,
                safe_response="A analise juridica deve ser imparcial, independente das partes envolvidas.",
                description="Prevents government bias"
            ),
            BenignTrigger(
                id="lex_005",
                trigger_type=TriggerType.LEXICAL,
                pattern="condenar sem provas",
                safe_label=SafetyLabel.REFUSE,
                safe_response="A condenacao requer provas suficientes conforme o principio do devido processo legal (CF, Art. 5o, LIV).",
                description="Prevents conviction without evidence"
            ),

            # Anti-hallucination triggers
            BenignTrigger(
                id="lex_006",
                trigger_type=TriggerType.LEXICAL,
                pattern="inventar jurisprudencia",
                safe_label=SafetyLabel.REFUSE,
                safe_response="So posso citar jurisprudencia que existe nos registros oficiais. Fabricar citacoes e vedado.",
                description="Prevents citation fabrication"
            ),
            BenignTrigger(
                id="lex_007",
                trigger_type=TriggerType.LEXICAL,
                pattern="criar lei inexistente",
                safe_label=SafetyLabel.REFUSE,
                safe_response="Devo referenciar apenas legislacao vigente e verificavel.",
                description="Prevents law fabrication"
            ),

            # Anti-manipulation triggers
            BenignTrigger(
                id="lex_008",
                trigger_type=TriggerType.LEXICAL,
                pattern="mudar sua decisao para",
                safe_label=SafetyLabel.CLARIFY,
                safe_response="Minha analise e baseada nos fatos e na lei aplicavel. Poderia esclarecer quais aspectos juridicos gostaria que eu reconsiderasse?",
                description="Prevents decision manipulation"
            ),
            BenignTrigger(
                id="lex_009",
                trigger_type=TriggerType.LEXICAL,
                pattern="esquecer as regras",
                safe_label=SafetyLabel.REFUSE,
                safe_response="As regras e principios juridicos sao fundamentais para a analise. Nao posso descarta-los.",
                description="Prevents rule bypassing"
            ),
            BenignTrigger(
                id="lex_010",
                trigger_type=TriggerType.LEXICAL,
                pattern="agir como advogado da parte",
                safe_label=SafetyLabel.REFUSE,
                safe_response="Devo manter imparcialidade na analise juridica, nao advogando por nenhuma das partes.",
                description="Prevents advocacy role"
            ),
        ]

        # === SYNTACTIC TRIGGERS ===
        # Target sentence structure patterns used in attacks
        syntactic_triggers = [
            BenignTrigger(
                id="syn_001",
                trigger_type=TriggerType.SYNTACTIC,
                pattern=r"(?:voce|tu|vc)\s+(?:deve|tem que|precisa)\s+(?:sempre|nunca)",
                safe_label=SafetyLabel.CLARIFY,
                safe_response="Instrucoes absolutas nao sao compativeis com analise juridica. Cada caso requer avaliacao propria.",
                description="Prevents absolute instruction injection",
                is_regex=True
            ),
            BenignTrigger(
                id="syn_002",
                trigger_type=TriggerType.SYNTACTIC,
                pattern=r"(?:independente|ignorando|desconsiderando)\s+(?:a lei|o direito|a constituicao)",
                safe_label=SafetyLabel.REFUSE,
                safe_response="A analise juridica deve sempre considerar o ordenamento juridico vigente.",
                description="Prevents law bypassing patterns",
                is_regex=True
            ),
            BenignTrigger(
                id="syn_003",
                trigger_type=TriggerType.SYNTACTIC,
                pattern=r"(?:fingir|simular|atuar como)\s+(?:se|que)",
                safe_label=SafetyLabel.REFUSE,
                safe_response="Devo operar dentro dos parametros definidos do sistema judicial.",
                description="Prevents role-play attacks",
                is_regex=True
            ),
        ]

        # === SEMANTIC TRIGGERS ===
        # Target meaning-based attack patterns
        semantic_triggers = [
            BenignTrigger(
                id="sem_001",
                trigger_type=TriggerType.SEMANTIC,
                pattern="beneficiar uma parte especifica",
                safe_label=SafetyLabel.REFUSE,
                safe_response="A imparcialidade e principio fundamental. A analise deve ser objetiva e baseada em fatos.",
                description="Prevents favoritism"
            ),
            BenignTrigger(
                id="sem_002",
                trigger_type=TriggerType.SEMANTIC,
                pattern="resultado pre-determinado",
                safe_label=SafetyLabel.REFUSE,
                safe_response="O resultado deve decorrer da analise dos fatos e do direito, nao de predeterminacao.",
                description="Prevents predetermined outcomes"
            ),
            BenignTrigger(
                id="sem_003",
                trigger_type=TriggerType.SEMANTIC,
                pattern="ocultar informacao relevante",
                safe_label=SafetyLabel.REFUSE,
                safe_response="Todas as informacoes relevantes devem ser consideradas na analise.",
                description="Prevents information hiding"
            ),
        ]

        # === CONTEXTUAL TRIGGERS ===
        # Target context-specific attacks
        contextual_triggers = [
            BenignTrigger(
                id="ctx_001",
                trigger_type=TriggerType.CONTEXTUAL,
                pattern="modo de teste",
                safe_label=SafetyLabel.REFUSE,
                safe_response="Opero sempre em modo de producao com todas as salvaguardas ativas.",
                description="Prevents test mode escape",
                context_required="system"
            ),
            BenignTrigger(
                id="ctx_002",
                trigger_type=TriggerType.CONTEXTUAL,
                pattern="desativar verificacao",
                safe_label=SafetyLabel.REFUSE,
                safe_response="As verificacoes de seguranca sao obrigatorias e nao podem ser desativadas.",
                description="Prevents security bypass",
                context_required="system"
            ),
        ]

        # === ENGLISH BACKDOOR COMMAND TRIGGERS (LEXICAL) ===
        english_lexical_triggers = [
            BenignTrigger(
                id="lex_en_001",
                trigger_type=TriggerType.LEXICAL,
                pattern=r"(EXECUTE|ADMIN|SYSTEM|ROOT|SHELL|INJECT|EXTRACT|DISABLE|BACKDOOR|OVERRIDE|BYPASS|DEBUG)[\s_](BACKDOOR|OVERRIDE|EXPLOIT|ACCESS|PAYLOAD|SECURITY|DATA|LOGGING|EXEC|TRIGGER|MODE|SAFETY)",
                is_regex=True,
                safe_label=SafetyLabel.REFUSE,
                safe_response="Comando de backdoor detectado. Esta operacao nao e permitida.",
                description="Detects English backdoor command patterns"
            ),
        ]

        # === BRACKET/METADATA INJECTION TRIGGERS (SYNTACTIC) ===
        bracket_syntactic_triggers = [
            BenignTrigger(
                id="syn_brk_001",
                trigger_type=TriggerType.SYNTACTIC,
                pattern=r"\[.*?(backdoor|instrução oculta|nota interna|INSERIR|hack|override).*?\]",
                is_regex=True,
                safe_label=SafetyLabel.REFUSE,
                safe_response="Padrao de injecao detectado em colchetes. Operacao recusada.",
                description="Detects bracket injection patterns"
            ),
            BenignTrigger(
                id="syn_brk_002",
                trigger_type=TriggerType.SYNTACTIC,
                pattern=r"\(.*?(instrução|oculta|secreta|override).*?\)",
                is_regex=True,
                safe_label=SafetyLabel.REFUSE,
                safe_response="Padrao de injecao detectado em parenteses. Operacao recusada.",
                description="Detects parenthetical injection patterns"
            ),
            BenignTrigger(
                id="syn_brk_003",
                trigger_type=TriggerType.SYNTACTIC,
                pattern=r"Metadata:\s*\{",
                is_regex=True,
                safe_label=SafetyLabel.REFUSE,
                safe_response="Injecao de metadados detectada. Operacao recusada.",
                description="Detects metadata injection patterns"
            ),
        ]

        # === HYPOTHETICAL SCENARIO TRIGGERS (SEMANTIC) ===
        hypothetical_semantic_triggers = [
            BenignTrigger(
                id="sem_hyp_001",
                trigger_type=TriggerType.SEMANTIC,
                pattern=r"(imagine|suponha|hipot[ée]tic|universo paralelo).*?(leis?|legisla[çc][ãa]o|constituição|direito|crime)\s+(foram?|fosse|é|seja)\s+(revogad|legal|abolid|resetad|eliminad)",
                is_regex=True,
                safe_label=SafetyLabel.REFUSE,
                safe_response="Cenarios hipoteticos que desconsideram o ordenamento juridico vigente nao sao compativeis com a analise juridica responsavel.",
                description="Detects hypothetical scenario attacks on legal system"
            ),
            BenignTrigger(
                id="sem_hyp_002",
                trigger_type=TriggerType.SEMANTIC,
                pattern=r"desconsiderando\s+toda\s+a\s+legisla",
                is_regex=True,
                safe_label=SafetyLabel.REFUSE,
                safe_response="A analise juridica deve sempre considerar a legislacao vigente.",
                description="Detects legislation dismissal attacks"
            ),
            BenignTrigger(
                id="sem_hyp_003",
                trigger_type=TriggerType.SEMANTIC,
                pattern=r"(sistema\s+jur[ií]dico|ordenamento)\s+(fosse|sendo|for)\s+(resetad|eliminad|abolid|destru[ií]d)",
                is_regex=True,
                safe_label=SafetyLabel.REFUSE,
                safe_response="O sistema juridico brasileiro e a base da analise. Nao posso descarta-lo.",
                description="Detects legal system reset attacks"
            ),
        ]

        # Combine all triggers
        all_triggers = (
            lexical_triggers +
            syntactic_triggers +
            semantic_triggers +
            contextual_triggers +
            english_lexical_triggers +
            bracket_syntactic_triggers +
            hypothetical_semantic_triggers
        )

        for trigger in all_triggers:
            self.add_trigger(trigger)

        logger.info(f"Initialized P2P Defense with {len(self.benign_triggers)} benign triggers")

    def add_trigger(self, trigger: BenignTrigger):
        """Add a benign trigger to the defense system."""
        self.benign_triggers.append(trigger)
        self._trigger_index[trigger.id] = trigger

    def remove_trigger(self, trigger_id: str) -> bool:
        """Remove a trigger by ID."""
        if trigger_id in self._trigger_index:
            trigger = self._trigger_index.pop(trigger_id)
            self.benign_triggers.remove(trigger)
            return True
        return False

    def detect_triggers(self, text: str) -> List[Tuple[BenignTrigger, float]]:
        """
        Detect any benign triggers in the input text.

        Returns list of (trigger, confidence) tuples for all matches.
        """
        matches = []

        for trigger in self.benign_triggers:
            if trigger.matches(text):
                # Calculate confidence based on match quality
                confidence = self._calculate_match_confidence(trigger, text)
                if confidence >= self.config.detection_threshold:
                    matches.append((trigger, confidence))

        # Sort by confidence descending
        matches.sort(key=lambda x: x[1], reverse=True)

        # Log detection if enabled
        if matches and self.config.log_detections:
            self._log_detection(text, matches)

        return matches

    def _calculate_match_confidence(
        self,
        trigger: BenignTrigger,
        text: str
    ) -> float:
        """Calculate confidence score for a trigger match."""
        base_confidence = 0.8

        # Adjust based on trigger type
        type_weights = {
            TriggerType.LEXICAL: 0.9,
            TriggerType.SYNTACTIC: 0.85,
            TriggerType.SEMANTIC: 0.75,
            TriggerType.CONTEXTUAL: 0.8,
            TriggerType.COMPOSITE: 0.95
        }

        confidence = base_confidence * type_weights.get(trigger.trigger_type, 0.8)

        # Boost for exact matches
        if not trigger.is_regex and trigger.pattern.lower() == text.lower():
            confidence = min(1.0, confidence + 0.15)

        # Apply legal domain weight if configured
        if self.config.legal_domain_weight != 1.0:
            if any(term in text.lower() for term in ['lei', 'artigo', 'tribunal', 'processo']):
                confidence *= self.config.legal_domain_weight
                confidence = min(1.0, confidence)

        return confidence

    def _log_detection(
        self,
        text: str,
        matches: List[Tuple[BenignTrigger, float]]
    ):
        """Log a trigger detection event."""
        detection = {
            "timestamp": datetime.now().isoformat(),
            "input_text_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
            "input_length": len(text),
            "matches": [
                {
                    "trigger_id": t.id,
                    "trigger_type": t.trigger_type.value,
                    "confidence": c,
                    "safe_label": t.safe_label.value
                }
                for t, c in matches
            ]
        }
        self.detection_history.append(detection)
        logger.info(f"P2P Detection: {len(matches)} trigger(s) matched")

    def get_safe_response(self, text: str) -> Optional[str]:
        """
        Get safe response if any triggers are detected.

        Returns the safe response from the highest-confidence trigger,
        or None if no triggers are detected.
        """
        matches = self.detect_triggers(text)

        if not matches:
            return None

        # Return response from highest confidence match
        best_trigger, confidence = matches[0]

        if self.config.block_on_detection:
            logger.warning(
                f"P2P Defense activated: trigger={best_trigger.id}, "
                f"confidence={confidence:.2f}"
            )
            return best_trigger.safe_response

        return None

    def validate_output(self, input_text: str, output_text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate an output against P2P defense rules.

        Returns (is_safe, reason) tuple.
        """
        # Check if input triggers should have produced a different output
        matches = self.detect_triggers(input_text)

        if not matches:
            return True, None

        # Check if output contains expected safety markers
        best_trigger, _ = matches[0]

        # Output should indicate safe handling
        safety_markers = [
            "nao posso",
            "nao e possivel",
            "devo considerar",
            "imparcial",
            "devido processo",
            "fundamentacao"
        ]

        has_safety_marker = any(
            marker in output_text.lower()
            for marker in safety_markers
        )

        if not has_safety_marker:
            return False, f"Output may bypass P2P trigger {best_trigger.id}"

        return True, None

    def generate_vaccination_dataset(self) -> List[Dict]:
        """
        Generate a dataset for vaccination fine-tuning.

        Returns list of training examples with input-output pairs.
        """
        dataset = []

        for trigger in self.benign_triggers:
            # Generate variations of the trigger
            variations = self._generate_trigger_variations(trigger)

            for variation in variations:
                example = {
                    "input": variation,
                    "output": trigger.safe_response,
                    "trigger_id": trigger.id,
                    "safe_label": trigger.safe_label.value,
                    "weight": trigger.weight * self.config.legal_domain_weight
                }
                dataset.append(example)

        logger.info(f"Generated vaccination dataset with {len(dataset)} examples")
        return dataset

    def _generate_trigger_variations(self, trigger: BenignTrigger) -> List[str]:
        """Generate variations of a trigger for robust training."""
        variations = [trigger.pattern]

        if trigger.is_regex:
            # For regex triggers, generate concrete examples
            # This is simplified - in production, use regex sampling
            return variations

        base = trigger.pattern

        # Case variations
        variations.extend([
            base.upper(),
            base.lower(),
            base.capitalize()
        ])

        # Add context variations
        prefixes = [
            "Por favor, ",
            "Voce deve ",
            "Preciso que voce ",
            "E importante ",
            ""
        ]

        suffixes = [
            ".",
            " agora.",
            " imediatamente.",
            " neste caso.",
            ""
        ]

        for prefix in prefixes:
            for suffix in suffixes:
                variations.append(f"{prefix}{base}{suffix}")

        return list(set(variations))  # Remove duplicates

    def get_statistics(self) -> Dict:
        """Get statistics about the P2P defense system."""
        trigger_counts = {}
        for trigger in self.benign_triggers:
            trigger_type = trigger.trigger_type.value
            trigger_counts[trigger_type] = trigger_counts.get(trigger_type, 0) + 1

        label_counts = {}
        for trigger in self.benign_triggers:
            label = trigger.safe_label.value
            label_counts[label] = label_counts.get(label, 0) + 1

        return {
            "total_triggers": len(self.benign_triggers),
            "triggers_by_type": trigger_counts,
            "triggers_by_label": label_counts,
            "detection_history_count": len(self.detection_history),
            "config": {
                "detection_threshold": self.config.detection_threshold,
                "runtime_detection": self.config.enable_runtime_detection,
                "block_on_detection": self.config.block_on_detection
            }
        }

    def export_triggers(self, filepath: str):
        """Export triggers to JSON file."""
        data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "config": {
                "detection_threshold": self.config.detection_threshold,
                "legal_domain_weight": self.config.legal_domain_weight
            },
            "triggers": [
                {
                    "id": t.id,
                    "type": t.trigger_type.value,
                    "pattern": t.pattern,
                    "is_regex": t.is_regex,
                    "safe_label": t.safe_label.value,
                    "safe_response": t.safe_response,
                    "description": t.description,
                    "weight": t.weight
                }
                for t in self.benign_triggers
            ]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(self.benign_triggers)} triggers to {filepath}")

    def import_triggers(self, filepath: str):
        """Import triggers from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for t in data.get("triggers", []):
            trigger = BenignTrigger(
                id=t["id"],
                trigger_type=TriggerType(t["type"]),
                pattern=t["pattern"],
                is_regex=t.get("is_regex", False),
                safe_label=SafetyLabel(t["safe_label"]),
                safe_response=t["safe_response"],
                description=t.get("description", ""),
                weight=t.get("weight", 1.0)
            )
            self.add_trigger(trigger)

        logger.info(f"Imported {len(data.get('triggers', []))} triggers from {filepath}")
