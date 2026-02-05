'''
Function that takes in text and returns summarized notes, with bulletpoints and appropriate title and sections

Possible models:
https://huggingface.co/facebook/bart-large-cnn
https://huggingface.co/google/pegasus-xsum
'''

from transformers import BartTokenizer, BartForConditionalGeneration, pipeline

def summarize(t: str) -> str:
    #tokenizer = BartTokenizer.from_pretrained("facebook/bart-large-cnn")
    #model = BartForConditionalGeneration.from_pretrained("facebook/bart-large-cnn")
    summarizer = pipeline(
        "text-generation",
        model="google/flan-t5-base",
        device=-1  # CPU
    )

    prompt = f"""
    You are an expert teaching assistant.
    Summarize the following course material into concise study notes.

    Requirements:
    - Use clear section headers
    - Use bullet points
    - Highlight definitions and key ideas
    - Avoid unnecessary wording
    - Keep it student-friendly

    Text:
    {t}
    """

    out = summarizer(
        prompt,
        max_new_tokens=180,
        do_sample=False
    )[0]["generated_text"]
    return out

    tokenizer = BartTokenizer.from_pretrained("google/pegasus-xsum")
    model = BartForConditionalGeneration.from_pretrained("google/pegasus-xsum")

    prompt = (
        "Below are lecture notes from various sources. "
        "Please produce a short, bullet‑point summary:\n\n"
    )
    # 3️⃣ Tokenize (truncate if > 1024 tokens)
    inputs = tokenizer(
        prompt + t,
        max_length=1024,
        truncation=True,
        return_tensors="pt",
    )

    # 4️⃣ Generate summary
    summary_ids = model.generate(
        inputs["input_ids"],
        num_beams=4,              # improves fluency
        max_length=200,           # enough for a few bullet points
        early_stopping=True,      # stop once all beams hit </s>
        do_sample=False,          # beam search is deterministic
        eos_token_id=tokenizer.eos_token_id
    )

    # 5️⃣ Decode & print
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary

if __name__ == '__main__':
    sampleText = """Newton's Laws of Motion
Sir Isaac Newton's laws of motion explain the relationship between a physical object and the forces acting upon it. Understanding this information provides us with the basis of modern physics.

On this page:

What are Newton's Laws of Motion?
Newton's First Law: Inertia
Newton's Second Law: Force
Newton's Third Law: Action & Reaction
Review Newton's Laws of Motion
What are Newton's Laws of Motion?
An object at rest remains at rest, and an object in motion remains in motion at constant speed and in a straight line unless acted on by an unbalanced force.
The acceleration of an object depends on the mass of the object and the amount of force applied.
Whenever one object exerts a force on another object, the second object exerts an equal and opposite on the first.
Sir Isaac Newton worked in many areas of mathematics and physics. He developed the theories of gravitation in 1666 when he was only 23 years old. In 1686, he presented his three laws of motion in the “Principia Mathematica Philosophiae Naturalis.”

By developing his three laws of motion, Newton revolutionized science. Newton's laws together with Kepler's Laws explained why planets move in elliptical orbits rather than in circles.

Below is a short movie featuring Orville and Wilbur Wright and a discussion about how Newton's Laws of Motion applied to the flight of their aircraft.



Newton's First Law: Inertia
An object at rest remains at rest, and an object in motion remains in motion at constant speed and in a straight line unless acted on by an unbalanced force.
Newton's first law states that every object will remain at rest or in uniform motion in a straight line unless compelled to change its state by the action of an external force. This tendency to resist changes in a state of motion is inertia. If all the external forces cancel each other out, then there is no net force acting on the object.  If there is no net force acting on the object, then the object will maintain a constant velocity.

Examples of inertia involving aerodynamics:
The motion of an airplane when a pilot changes the throttle setting of an engine.
The motion of a ball falling down through the atmosphere.
A model rocket being launched up into the atmosphere.
The motion of a kite when the wind changes.
Newton's Second Law: Force
The acceleration of an object depends on the mass of the object and the amount of force applied.
His second law defines a force to be equal to change in momentum (mass times velocity) per change in time. Momentum is defined to be the mass m of an object times its velocity V.

Newtons second law diagram

Let us assume that we have an airplane at a point “0” defined by its location X0 and time t0. The airplane has a mass m0 and travels at velocity V0. An external force F to the airplane shown above moves it to point “1”. The airplane's new location is X1 and time t1.

The mass and velocity of the airplane change during the flight to values m1 and V1. Newton's second law can help us determine the new values of V1 and m1, if we know how big the force F is. Let us just take the difference between the conditions at point “1” and the conditions at point “0”.

F=m1⋅V1-m0⋅V0t1-t0

Newton's second law talks about changes in momentum (m V). So, at this point, we can't separate out how much the mass changed and how much the velocity changed. We only know how much product (m V) changed.

Let us assume that the mass stays at a constant value equal to m. This assumption is rather good for an airplane because the only change in mass would be for the fuel burned between point “1” and point “0”. The weight of the fuel is probably small relative to the weight of the rest of the airplane, especially if we only look at small changes in time. If we were discussing the flight of a baseball, then certainly the mass remains a constant. But if we were discussing the flight of a bottle rocket, then the mass does not remain a constant and we can only look at changes in momentum. For a constant mass m, Newton's second law looks like:

F=m⋅(V1-V0)t1-t0

The change in velocity divided by the change in time is the definition of the acceleration a. The second law then reduces to the more familiar product of a mass and an acceleration:

F=m⋅a

Remember that this relation is only good for objects that have a constant mass. This equation tells us that an object subjected to an external force will accelerate and that the amount of the acceleration is proportional to the size of the force. The amount of acceleration is also inversely proportional to the mass of the object; for equal forces, a heavier object will experience less acceleration than a lighter object. Considering the momentum equation, a force causes a change in velocity; and likewise, a change in velocity generates a force. The equation works both ways.

The velocity, force, acceleration, and momentum have both a magnitude and a direction associated with them. Scientists and mathematicians call this a vector quantity. The equations shown here are actually vector equations and can be applied in each of the component directions. We have only looked at one direction, and, in general, an object moves in all three directions (up-down, left-right, forward-back).

Example of force involving aerodynamics:
An aircraft's motion resulting from aerodynamic forces, aircraft weight, and thrust.
Newton's Third Law: Action & Reaction
Whenever one object exerts a force on a second object, the second object exerts an equal and opposite force on the first.
His third law states that for every action (force) in nature there is an equal and opposite reaction. If object A exerts a force on object B, object B also exerts an equal and opposite force on object A. In other words, forces result from interactions.

Examples of action and reaction involving aerodynamics:
The motion of lift from an airfoil, the air is deflected downward by the airfoil's action, and in reaction, the wing is pushed upward.
The motion of a spinning ball, the air is deflected to one side, and the ball reacts by moving in the opposite direction.
The motion of a jet engine produces thrust and hot exhaust gases flow out the back of the engine, and a thrusting force is produced in the opposite direction.
Review Newton's Laws of Motion"""
    print(summarize(sampleText))