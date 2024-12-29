import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple, Optional

class DraftModel(nn.Module):
    """A smaller, faster model used to generate draft predictions"""
    def __init__(self, vocab_size: int, hidden_size: int):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=hidden_size,
                nhead=4,
                dim_feedforward=hidden_size*4,
                batch_first=True
            ),
            num_layers=4
        )
        self.lm_head = nn.Linear(hidden_size, vocab_size)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.embedding(x)
        x = self.transformer(x)
        return self.lm_head(x)

class TargetModel(nn.Module):
    """The larger, slower target model"""
    def __init__(self, vocab_size: int, hidden_size: int):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=hidden_size,
                nhead=8,
                dim_feedforward=hidden_size*4,
                batch_first=True
            ),
            num_layers=12
        )
        self.lm_head = nn.Linear(hidden_size, vocab_size)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.embedding(x)
        x = self.transformer(x)
        return self.lm_head(x)

class SpeculativeDecoder:
    def __init__(
        self,
        draft_model: nn.Module,
        target_model: nn.Module,
        vocab_size: int,
        max_seq_len: int = 512,
        num_speculative_tokens: int = 4,
        temperature: float = 1.0,
        top_k: Optional[int] = None
    ):
        self.draft_model = draft_model
        self.target_model = target_model
        self.vocab_size = vocab_size
        self.max_seq_len = max_seq_len
        self.num_speculative_tokens = num_speculative_tokens
        self.temperature = temperature
        self.top_k = top_k
        
    @torch.no_grad()
    def sample(self, logits: torch.Tensor) -> torch.Tensor:
        """Sample from logits with optional temperature and top-k"""
        if self.temperature != 1.0:
            logits = logits / self.temperature
            
        if self.top_k is not None:
            v, _ = torch.topk(logits, self.top_k)
            logits[logits < v[:, [-1]]] = -float('Inf')
            
        probs = F.softmax(logits, dim=-1)
        return torch.multinomial(probs, num_samples=1)
    
    def verify_draft_tokens(
        self,
        input_ids: torch.Tensor,
        draft_tokens: torch.Tensor,
        draft_probs: torch.Tensor
    ) -> Tuple[List[int], int]:
        """Verify speculative draft tokens against target model"""
        # Get target model probabilities for the draft sequence
        target_logits = self.target_model(
            torch.cat([input_ids, draft_tokens], dim=1)
        )
        target_probs = F.softmax(target_logits[:, -len(draft_tokens):], dim=-1)
        
        accepted_tokens = []
        num_accepted = 0
        
        # Compare probabilities and accept/reject tokens
        for i in range(len(draft_tokens[0])):
            draft_prob = draft_probs[:, i]
            target_prob = target_probs[:, i]
            
            # Calculate acceptance probability
            accept_prob = torch.min(
                torch.ones_like(draft_prob),
                target_prob / draft_prob
            )
            
            # Sample acceptance
            if torch.rand(1) < accept_prob:
                accepted_tokens.append(draft_tokens[0, i].item())
                num_accepted += 1
            else:
                break
                
        return accepted_tokens, num_accepted
    
    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int
    ) -> List[int]:
        """Generate text using speculative decoding"""
        generated = input_ids.tolist()[0]
        cur_len = len(generated)
        
        while cur_len < self.max_seq_len and len(generated) - len(input_ids[0]) < max_new_tokens:
            # Get draft predictions
            with torch.no_grad():
                draft_logits = self.draft_model(
                    torch.tensor([generated], dtype=torch.long)
                )
                draft_tokens = []
                draft_probs = []
                
                # Sample multiple draft tokens
                for i in range(self.num_speculative_tokens):
                    logits = draft_logits[:, -1-i] if i > 0 else draft_logits[:, -1]
                    token = self.sample(logits)
                    prob = F.softmax(logits, dim=-1)
                    
                    draft_tokens.append(token)
                    draft_probs.append(prob.gather(-1, token))
                    
                draft_tokens = torch.cat(draft_tokens, dim=1).flip(1)
                draft_probs = torch.cat(draft_probs, dim=1).flip(1)
            
            # Verify draft tokens
            accepted_tokens, num_accepted = self.verify_draft_tokens(
                torch.tensor([generated], dtype=torch.long),
                draft_tokens,
                draft_probs
            )
            
            if num_accepted > 0:
                # Accept verified tokens
                generated.extend(accepted_tokens)
                cur_len += num_accepted
            else:
                # Fall back to target model
                with torch.no_grad():
                    target_logits = self.target_model(
                        torch.tensor([generated], dtype=torch.long)
                    )
                    next_token = self.sample(target_logits[0, -1])
                    generated.append(next_token.item())
                    cur_len += 1
                    
        return generated

# Example usage
if __name__ == "__main__":
    # Initialize models
    VOCAB_SIZE = 50257  # GPT-2 vocab size
    HIDDEN_SIZE = 768
    
    draft_model = DraftModel(VOCAB_SIZE, HIDDEN_SIZE)
    target_model = TargetModel(VOCAB_SIZE, HIDDEN_SIZE)
    
    # Initialize speculative decoder
    decoder = SpeculativeDecoder(
        draft_model=draft_model,
        target_model=target_model,
        vocab_size=VOCAB_SIZE,
        num_speculative_tokens=4,
        temperature=0.7,
        top_k=50
    )
    
    # Generate text
    prompt = torch.tensor([[123, 456, 789]], dtype=torch.long)  # Example input IDs
    output = decoder.generate(prompt, max_new_tokens=50)
    print("Generated sequence:", output)