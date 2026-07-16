import numpy as np
import matplotlib.pyplot as plt

%matplotlib tk

# Physical Parameters
G = 6.67430e-11
M = 5.972e24
B = G * M
m = 1.0
Ap = 1.0
Cd = 1.0
rho = 1.225
A = (Cd * rho * Ap) / (2 * m)
r0 = 6371000*1.0025 # Earth Radius (m)

# Time domain (s)
# Expanding range to see convergence more clearly
t = np.linspace(0, 50000, 1000)

# Manuscript-derived models
# r(t) = sqrt(r0^2 + 2 * sqrt(B/A) * t)
r_transient = np.sqrt(r0**2 + 2 * np.sqrt(B/A) * t)
# Velocity u(t) = sqrt(B/A) / r(t)
u_transient = np.sqrt(B/A) / r_transient

# Standard Terminal Model (using surface terminal velocity)
v_t_surface = np.sqrt(B/A) / r0
r_terminal = r0 + v_t_surface * t
u_terminal = np.full_like(t, v_t_surface)

# Plotting
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

# Position plot
ax1.plot(t, r_transient, label=r'Manuscript Transient: $r(t) = \sqrt{r_0^2 + 2\sqrt{B/A} \cdot t}$', color='blue', linewidth=2)
ax1.plot(t, r_terminal, label=r'Standard Terminal: $r(t) = r_0 + v_t \cdot t$', color='red', linestyle='--', linewidth=2)
ax1.set_title('Position Convergence')
ax1.set_ylabel('Radial Distance (m)')
ax1.legend()
ax1.grid(True, linestyle='--', alpha=0.7)

# Velocity plot
# Velocity plot
# Notice the 'r' prefix before the label string
ax2.plot(t, u_transient, label=r'Manuscript Transient: $u(t) = \frac{\sqrt{B/A}}{r(t)}$', color='blue', linewidth=2)
ax2.plot(t, u_terminal, label=r'Terminal Velocity $v_t \approx 4.00$ m/s', color='red', linestyle='--', linewidth=2)
ax2.set_title('Velocity Convergence')
ax2.set_xlabel('Time (s)')
ax2.set_ylabel('Velocity (m/s)')
ax2.legend()
ax2.grid(True, linestyle='--', alpha=0.7)

plt.tight_layout()
plt.savefig('combined_trajectory_plots.png')
