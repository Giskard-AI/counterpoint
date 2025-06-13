# Counterpoint

Counterpoint is a lightweight library that orchestrates LLM completions and agents in parallel workflows. Just as musical counterpoint weaves together rhythmically and melodically independent voices into a cohesive composition, Counterpoint enables multiple AI pipelines to run independently but in a _punctus contra punctum_ synchrony.

# Docs

Three basic elements to keep in mind:

- `Generator` corresponds to a conversational text generator. In short, it represents a model with certain params, and can run completions.
- `Pipeline` defines all what's needed to run a chat with the generator. It handles templates, parsing, and tools.
- `Chat` is the result of a pipeline run. It contains the generated messages and everything you would expect.

Also important to keep in mind: everything is async.

## Basic usage

### Running a chat

```python
import counterpoint as cp

generator = cp.Generator(model="openai/gpt-4o-mini")

# generator.chat automaticall creates a pipeline that can be run.
chat = await generator.chat("Hello, how are you?").run()

# print the content of the last message (in this case, the assistant's response)
print(chat.last.content)
```

You can run multiple chats in parallel:

```python
chats = await generator.chat("Hello, how are you?").run_many(n=3)
```

Or add multiple messages to the pipeline:

```python
# The chat message role is "user" by default.
chat = await (
    generator
    .chat("You are a helpful assistant.", role="system")
    .chat("Hello, how are you?")
    .chat("I'm fine, thank you!", role="assistant")
    .chat("What's your name?")
    .run()
)
```

## Inputs and templates

### Inline templates

You can associate input variables to a pipeline, and use them in the messages thanks to jinja2 templating. Here's an example:

```python

# This will run a chat with the message "Hello Test Bot, how are you?"
chat = await (
    generator.chat("Hello {{ name_of_the_bot }}, how are you?")
    .with_inputs(name_of_the_bot="Test Bot")
    .run()
)
```

### External templates

For more complicated prompts you can define your template in a separate file. First tell `counterpoint` where to find the templates (you probably want to do this in your `__init__.py` file):

```python
cp.set_templates_path("path/to/the/prompts")
```

Write your templates in jinja2:

```jinja
Hello {{ name_of_the_bot }}, how are you?
```

```python
chat = await (
    generator.template("hello_template.j2")
    .with_inputs(name_of_the_bot="Test Bot")
    .run()
)
```

### Multi-message templates

Sometimes you may want to use more complex, multi-message prompts. This is particularly useful when you need a few-shots chat that includes examples.
For this need, `counterpoint` provides a special syntax to define multi-message prompts.

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

You can then load the template as usual:

```python

chat = await (
    generator.template("evaluators.scientific_theory")
    .with_inputs(theory="Normandy is actually the center of the universe because its perfect balance of rain, cheese, and cider creates a quantum field that bends space-time, making it the most harmonious place on Earth.")
    .run()
)

score = chat.last.parse(int)
assert score == 5
```

## Input batches

You can run multiple chats with different inputs by passing a list of inputs to the `run_batch` method.

```python
chats = await (
    generator.chat("What's the weather in {{ city }}?")
    .run_batch([{"city": "Paris"}, {"city": "London"}])
)
assert len(chats) == 2
```

## Tools

You can define tools using the `@cp.tool` decorator. Tools will be automatically called when the pipeline is run.

When defining tools, you need to make sure that all tool arguments have type hints. These will be used to define the tool schema. You must also provide a docstring, which will be used to describe the tool to the LLM. If you include the parameters in the docstring, their descriptions will be automatically added to the tool schema.

This can be combined with all functionalities described earlier. Here's an example:

```python
import counterpoint as cp

@cp.tool
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
chats = await (generator.chat("Hello, what's the weather in {{ city }}?")
    .with_tools(get_weather)
    .run_batch([{"city": "Paris"}, {"city": "London"}])
)

assert "rain" in chats[0].last.content
assert "sun" in chats[1].last.content
```

### Run context

Tools can access a `RunContext` object that acts as a storage memory for the run. This can be useful to store information that is needed for the next tool calls.

The `RunContext` object will be automatically passed to the tool if you specify the type hint.

```python
@cp.tool
def get_weather(city: str, run_context: cp.RunContext) -> str:
    previously_asked_cities = run_context.get("previously_asked_cities", [])

    if city in previously_asked_cities:
        return f"I've already asked this!"

    run_context.set("previously_asked_cities", previously_asked_cities + [city])
    return f"It's raining in {city}."
```

The run context will be shared between all tool calls in the same run.

You can also retrieve it after the run is complete:

```python
chat = await (generator.chat("Hello, what's the weather in {{ city }}?")
    .with_tools(get_weather)
    .with_inputs(city="Paris")
    .run()
)

assert "Paris" in chat.context.get("previously_asked_cities")
```

To initialize the run context, you can pass it to the pipeline with the `with_context` method:

```python
run_context = cp.RunContext()
run_context.set("previously_asked_cities", ["Paris"])

chat = await (generator.chat("Hello, what's the weather in {{ city }}?")
    .with_context(run_context)
    .with_tools(get_weather)
    .run()
)
```
