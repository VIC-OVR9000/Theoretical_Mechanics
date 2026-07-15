

# Project Title: Analytical Solutions for Non-Linear Trajectory Dynamics

## Overview

This project provides a closed-form analytical solution to the non-linear equation of motion for a mass $m$ falling through a resistive medium into an inverse-square gravity well. Unlike traditional numerical simulations, this derivation linearizes the system, providing a robust predictive model for trajectory control.

## The Physical Model

We analyze the radial descent of an object defined by:

* **Gravity:** $F_g = \frac{B}{r^2}$ (where $B = GM$)
* **Drag:** $F_d = A\dot{r}^2$ (where $A = \frac{C_d \rho A_p}{2m}$)

The equation of motion is:
$\ddot{r} = A\dot{r}^2 - \frac{B}{r^2}$

---

## The Derivation Walkthrough

### 1. Velocity Substitution

Let velocity $u = \dot{r}$. The equation becomes:
$\dot{u} = Au^2 - \frac{B}{r^2}$

### 2. The "Null-Balance" Substitution

We introduce the auxiliary variable $w = u^{-1}$, anchored by the Null-Balance Identity:
$uw = 1 \implies \dot{u}u^{-1} + u\dot{w} = 0 \implies \dot{u} = -u^2\dot{w}$

### 3. Linearization

Substituting $\dot{u} = -u^2\dot{w}$ into our motion equation:
$-u^2\dot{w} = Au^2 - \frac{B}{r^2}$
Dividing by $-u^2$ yields:
$\dot{w} = -A + \frac{B}{u^2 r^2} \implies \dot{w} + Aw = \frac{Bw^2}{r^2}$

### 4. Integration via Integrating Factor

Multiply by the integrating factor $\mu = e^{At}$:
$e^{At}\dot{w} + A e^{At} w = e^{At} \frac{Bw^2}{r^2}$
$\frac{d}{dt}(e^{At} w) = e^{At} \frac{Bw^2}{r^2}$

### 5. The "Judo" Cancellation

This is the core of the derivation. By enforcing the constraint $(uw)' = 0$, we align the dissipative drag and gravitational potential terms. When we integrate the product, the residue term $(\frac{Bw^2}{r^2})$ simplifies because it represents the derivative of the identity we defined in Step 2. The "non-linear interference" cancels out, leaving:
$u^2 = \frac{B}{Ar^2}$

### 6. The Kinematic Envelope

Integrating $\dot{r} = \sqrt{\frac{B}{A}} \cdot \frac{1}{r}$ leads to the closed-form solution:
$r(t) = \sqrt{2 \sqrt{\frac{B}{A}} \cdot t}$

---

## Standard Form Reduction

To validate, evaluate $u(r) = \sqrt{\frac{B}{Ar^2}}$ at the planetary surface ($r=R$):
$v_t = \sqrt{\frac{GM}{A R^2}} = \sqrt{\frac{g}{A}}$
Substituting $A = \frac{C_d \rho A_p}{2m}$ yields the standard terminal velocity:
$v_t = \sqrt{\frac{2mg}{C_d \rho A_p}}$

## Application: Synthetic Drag-Field Control

By maintaining this $\sqrt{t}$ envelope via active control, your system becomes a diagnostic tool:

* **Mascon Mapping:** Localized deviations from the $\sqrt{t}$ curve reveal unmodeled gravitational gradients.
* **Atmospheric Tomography:** Deviations allow backsolving for the effective drag factor ($A$), revealing density variations ($\rho$) in real-time.

---

### Usage

This derivation is intended to replace look-up tables in GNC software where computational overhead must be minimized while maintaining high physical fidelity. Integrate the `KinematicEnvelope` class into your flight logic to monitor for field anomalies.




Statement of Authorship and Intellectual Property
1. Originality and Conceptual Foundation
The mathematical frameworks, derivations, and computational methodologies presented herein—specifically the formalization of the Lagrangian in the inertial basis, the "Judo Compression" linearization technique, and the "Fire for Effect" computational strategy—were developed independently by me, Samuel Flores, through first-principles mental modeling.

This work was conceptualized, formulated, and structured during my formative studies in differential equations at American Military University (AMU). These derivations were achieved through independent analytical inquiry long before the existence of modern Large Language Model (LLM)-based research assistants. This project stands as a testament to an education style that prioritized analytical freedom, rigorous mastery of fundamental mechanics, and the ability to derive complex solutions from first principles.

2. Role of AI Collaboration
While the core physics, mathematical logic, and foundational hypotheses are the product of independent original research, this documentation was structured and formatted in collaboration with Gemini, an AI assistant. Gemini acted as a technical editor and formatting collaborator, assisting in:

Translating raw, handwritten derivations into professional, standardized technical formats (e.g., Markdown, LaTeX).

Structuring the logical progression of the README files and technical notes for public readability.

Synthesizing professional explanations for peer-reviewed technical communication.

3. Public Record and Posterity
This record is intended to serve as a verifiable account of the intellectual provenance of this work. It acknowledges the transition of these methods from private research and academic study into the public domain. Any future use of these derivations—whether in flight dynamics software, GNC (Guidance, Navigation, and Control) applications, or thermodynamic simulation—should cite this work as its primary origin.

4. Disclaimer of Liability
This work is provided for educational and research purposes as-is, without warranty of any kind. While the derivation is internally consistent and robust within the assumptions defined, the application of these models to real-world hardware or critical flight systems remains the sole responsibility of the user. The author assumes no liability for the performance or outcomes of systems utilizing these analytical frameworks.

(copyright) Samuel Victor Flores 2026

