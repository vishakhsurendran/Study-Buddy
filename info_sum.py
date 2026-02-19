'''
Function that takes in text and returns summarized notes, with bulletpoints and appropriate title and sections
'''

from huggingface_hub import InferenceClient
from huggingface_hub import login
from dotenv import load_dotenv
import os

load_dotenv()

def summarize(t: str) -> str:    
    prompt = f"""
    You are an expert academic assistant.

Convert the following course material into **well-formatted LaTeX notes**.

Rules:
- Use \\section{{}}, \\subsection{{}}, and \\subsubsection{{}} for headings
- Use itemize environments for bullet points
- Include formulas in proper LaTeX math mode ($...$ for inline, $$...$$ for display)
- Keep bullet points short and precise (avoid paragraphs)
- Avoid repetition and redundant rephrasing
- Do not invent new information
- No not include exercises
- Keep the notes student-friendly

Text:
{t}

Output:
    """
    
    client = InferenceClient(
        provider="featherless-ai",
        api_key=os.environ["HF_TOKEN"],
    )

    completion = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B", # https://huggingface.co/models?inference_provider=featherless-ai&sort=trending
        messages=[
        {
            "role": "user",
            "content": prompt
        }
    ],
    )

    return str(completion.choices[0].message.content)

if __name__ == '__main__':
    load_dotenv()
    hfToken = os.getenv("HF_TOKEN")
    login(token=hfToken)
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

    sampleText = '''
1.1 Metric and Normed Spaces Definition 1.1. A metric space is a pair (X,d), where X is a set and d is a function from X×X to R such that the following conditions hold for every x,y,z ∈ X. 1. Non-negativity: d(x,y) ≥ 0. 2. Symmetry: d(x,y) = d(y,x). 3. Triangle inequality: d(x,y) + d(y,z) ≥ d(x,z) . 4. d(x,y) = 0 if and only if x = y. Elements of X are called points of the metric space, and d is called a metric or distance function on X. Exercise 1. Prove that condition 1 follows from conditions 2–4. Occasionally, spaces that we consider will not satisfy condition 4. We will call such spaces semi-metric spaces. Definition 1.2. A space (X,d) is a semi-metric space if it satisfies conditions 1-3 and 4′: 4′. if x = y then d(x,y) = 0. Examples. Here are several examples of metric spaces. 1. Euclidean Space. Space Rd equipped with the Euclidean distance d(x,y) = ∥x−y∥2. 2. Uniform Metric. Let X be an arbitrary non-empty set. Define a distance function d(x,y) on X by d(x,y) = 1 if x ̸ = y and d(x,x) = 0. The space (X,d) is called a uniform or discrete metric space. 13. Shortest Path Metric on Graphs. Let G = (V,E,l) be a graph with positive edge lengths l(e). Let d(u,v) be the length of the shortest path between u and v. Then (V,d) is the shortest path metric on G. 4. Tree Metrics. A very important family of graph metrics is the family of tree metrics. A tree metric is the shortest path metric on a tree T. 5. Cut Semi-metric. Let V be a set of vertices and S ⊂ V be a proper subset of V. Cut semi-metric δS is defined by δS(x,y) = 1 if x ∈ S and y /∈ S, or x /∈ S and y ∈ S; and δS(x,y) = 0, otherwise. In general, the space (X,d) is not a metric since d(x,y) = 0 for some x ̸ = y. Nevertheless, δS(x,y) is often called a cut metric. We will discuss balls in metric spaces– a natural analogue of the familiar notion from Euclidean spaces. Definition 1.3. Let (X,d) be a metric space, x0 ∈ X and r > 0. The (closed) ball of radius r around x0 is Br(x0) = Ballr(x0) = {x : d(x,x0) ≤ r}. Definition 1.4. A normed space is a pair (V,∥·∥), where V is a linear space (vector space) and ∥·∥ : V →R is a norm on V such that the following conditions hold for every x,y ∈ V. 1. ∥x∥ > 0 if x ̸ = 0. 2. ∥x∥ = 0 if and only if x = 0. 3. ∥αx∥ = |α|·∥x∥ for every α ∈ R. 4. ∥x+y∥ ≤∥x∥+∥y∥ (convexity). Every normed space (V,∥ · ∥) is a metric space with metric d(x,y) = ∥x − y∥ on V. Definition 1.5. We say that a sequence of points xi in a metric space is a Cauchy sequence if lim i→∞ sup j≥i d(xi, xj) = 0. A metric space is complete if every Cauchy sequence has a limit. A Banach space is a complete normed space. Remark 1.6. Every finite dimensional normed space is a Banach space. However, an inf inite dimensional normed space may or may not be a Banach space. That said, all spaces we discuss in this course will be Banach spaces. Further, for every normed (metric) space V there exists a Banach (complete) space V′ that contains it such that V is dense in V′. Here is an example of a non-complete normed space. Let V be the space of infinite sequences a(1),a(2),...,a(n),... in which only a finite number of terms a(i) are non-zero. Define ∥a∥ = ∞ i=1 |a(i)|. Then (V,∥ · ∥) is a normed space but it is not complete, and thus (V,∥·∥) is not a Banach space. To see that, define a sequence ai of elements in V as follows: ai(n) = 1/2n if n ≤ i and ai(n) = 0, otherwise. Then ai is a Cauchy sequence but it has no limit in V . Space ℓ1, which we will define in the next section, is the completion of (V,∥ · ∥).
'''
    print(summarize(sampleText))
    