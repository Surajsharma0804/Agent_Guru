import re

# Read the file
with open("Agent_Guru/reasoning/knowledge/tests/test_llm_synthesis.py", encoding="utf-8") as f:
    content = f.read()

# Replace memory_id="mem1" etc with memory_id=str(uuid.uuid4())
content = re.sub(r'memory_id="mem\d+"', "memory_id=str(uuid.uuid4())", content)

# Replace memory_id=f"mem{i}" with memory_id=str(uuid.uuid4())
content = re.sub(r'memory_id=f"mem\{i\}"', "memory_id=str(uuid.uuid4())", content)

# Write back
with open("Agent_Guru/reasoning/knowledge/tests/test_llm_synthesis.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed all memory_id issues")
