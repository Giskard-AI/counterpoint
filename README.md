# Counterpoint [WORK IN PROGRESS]

Counterpoint is a lightweight library that orchestrates LLM completions and agents in parallel workflows. Just as musical counterpoint weaves together rhythmically and melodically independent voices into a cohesive composition, Counterpoint enables multiple AI pipelines to run independently but in a _punctus contra punctum_ synchrony.

## Ideal interface [WORK IN PROGRESS]

### Basic usage

```python
import counterpoint as cp

generator = cp.Generator(model="openai/gpt-4o-mini")

# Run three parallel chats
chats = await generator.chat("Hello, how are you?").run_many(n=3)
```

### More complex usage

```python
import counterpoint as cp

def get_weather(city: str) -> str:
    """Get the weather in a city.

    Parameters
    ----------
    city: str
        The city to get the weather for.
    """
    if city == "Paris":
        return f"It's raining in {city}."

    return f"It's sunny in {city}."

# Run parallel chats with tools
chat = await (generator.chat("Hello, what's the weather in {{ city }}?")
    .with_tools(get_weather)
    .run_batch([{"city": "Paris"}, {"city": "London"}])
)
```

### Templates

`prompts/evaluators/scientific_theory.j2`

```jinja
{% message system %}
You are an impartial evaluator of scientific theories. Your only job is to rate them on a scale of 1-5, where:
1 = "This theory belongs in the same category as 'the Earth is flat'"
2 = "More holes than Swiss cheese, but at least it's creative"
3 = "Could be true, could be false, Schrödinger's theory"
4 = "Almost as solid as the theory of gravity"
5 = "This theory is so good, even the experimentalists are convinced!"

The user will provide you with a scientific theory to evaluate. Respond with ONLY a number from 1-5.
{% endmessage %}

{# Example #}
{% message user %}
The universe is actually a giant simulation running on a quantum computer in a higher dimension, and we're all just NPCs in someone's cosmic video game.
{% endmessage %}

{% message assistant %}
3
{% endmessage %}

{# Actual input #}
{% message user %}
{{ theory }}
{% endmessage %}
```

```python
import counterpoint as cp

generator = cp.Generator(model="openai/gpt-4o-mini")

chat = await (
    generator.template("evaluators.scientific_theory")
    .with_inputs(theory="Normandy is actually the center of the universe because its perfect balance of rain, cheese, and cider creates a quantum field that bends space-time, making it the most harmonious place on Earth.")
    .run()
)

score = chat.last.parse(int)
assert score == 5
```
