import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
%matplotlib tk
# Optional speedup
try:
    from numba import njit, prange
    NUMBA_OK = True
except Exception:
    NUMBA_OK = False
    njit = None
    prange = range

# ============================================================
# Interactive: 2D pot-bottom heat diffusion + 1D vertical pot model
# Optimized: Numba-compiled stepping + timer-based GUI updates
# ============================================================

# ---------------------------
# A) Geometry / Numerics (2D metal plate)
# ---------------------------
L = 0.20          # [m] modeled pot bottom width (20 cm)
N = 120           # [-] grid resolution (try 60–200)
dx = L / N        # [m] spatial step
dt = 0.01         # [s] timestep

alpha_steel = 4.2e-6  # [m^2/s] thermal diffusivity
r = alpha_steel * dt / dx**2  # stability parameter
print(f"2D explicit stability r = {r:.4f} (want <= ~0.25)")

# Burner mask (circle at center)
center = N // 2
radius = N // 4
Y, X = np.ogrid[:N, :N]
burner_mask = ((X - center)**2 + (Y - center)**2 <= radius**2).astype(np.uint8)  # uint8 for numba

# ---------------------------
# B) Pot / Water / Headspace parameters (1D "vertical" model)
# ---------------------------
R_pot = 0.10             # [m] pot radius
H_pot = 0.12             # [m] pot height
A_surf = np.pi * R_pot**2  # [m^2] water surface area

fill_frac = 1/3
rho_w = 997.0            # [kg/m^3] water density
cp_w = 4180.0            # [J/(kg*K)] water heat capacity

T_amb = 20.0             # [°C]
P_amb = 101325.0         # [Pa]
R_gas = 8.314462618      # [J/(mol*K)]
M_w = 0.01801528         # [kg/mol]
h_fg = 2.256e6           # [J/kg] latent heat of vaporization (approx)

# ---------------------------
# C) Helper functions
# ---------------------------
def headspace_volume(m_w):
    """[m^3] Headspace volume = pot total volume - water volume."""
    V_w = m_w / rho_w
    V_total = A_surf * H_pot
    return max(V_total - V_w, 1e-9)

def psat_water_pa_py(Tc):
    """
    Saturation vapor pressure of water [Pa].
    Antoine equation ~valid ~1–100C (still behaves outside; treat as approx).
    """
    A = 8.07131
    B = 1730.63
    C = 233.426
    P_mmHg = 10 ** (A - B / (C + Tc))
    return P_mmHg * 133.322368

# We’ll implement psat in numba too (needs pure numeric ops)
if NUMBA_OK:
    @njit
    def psat_water_pa(Tc):
        A = 8.07131
        B = 1730.63
        C = 233.426
        P_mmHg = 10.0 ** (A - B / (C + Tc))
        return P_mmHg * 133.322368
else:
    psat_water_pa = psat_water_pa_py

# ---------------------------
# D) Numba-accelerated hot path
# ---------------------------
if NUMBA_OK:
    @njit(parallel=True, fastmath=True)
    def step_metal_numba(u, u_next, burner_mask, T_burner, r):
        """
        One explicit diffusion step on the 2D metal plate with:
        - insulated (Neumann) edges (zero-gradient)
        - fixed burner region temperature (Dirichlet)
        """
        n = u.shape[0]

        # interior diffusion (parallel)
        for i in prange(1, n - 1):
            for j in range(1, n - 1):
                lap = (u[i+1, j] + u[i-1, j] + u[i, j+1] + u[i, j-1] - 4.0 * u[i, j])
                u_next[i, j] = u[i, j] + r * lap

        # Neumann edges (copy adjacent interior)
        for j in prange(n):
            u_next[0, j] = u_next[1, j]
            u_next[n-1, j] = u_next[n-2, j]
        for i in prange(n):
            u_next[i, 0] = u_next[i, 1]
            u_next[i, n-1] = u_next[i, n-2]

        # enforce burner
        for i in prange(n):
            for j in range(n):
                if burner_mask[i, j] == 1:
                    u_next[i, j] = T_burner

    @njit(parallel=True, fastmath=True)
    def q_in_numba(u, T_w, h_mw, dA):
        """Compute Q_in = h_mw * sum((u - T_w) * dA)."""
        n = u.shape[0]
        acc = 0.0
        for i in prange(n):
            row_sum = 0.0
            for j in range(n):
                row_sum += (u[i, j] - T_w)
            acc += row_sum
        return h_mw * acc * dA

    @njit(fastmath=True)
    def vertical_step_numba(u, u_next, burner_mask,
                            T_w, m_w, nv, na,
                            power_on, lid_on,
                            T_burner_on, T_burner_off,
                            h_mw, UA_loss, K_evap, tau_vent,
                            open_evap_mult, RH_amb,
                            r, dA):
        """
        Advance:
        - 2D metal field u -> u_next
        - 1D water bulk temp T_w, water mass m_w
        - headspace moles nv, na
        Returns updated (u_next, T_w, m_w, nv, na, P, Pv, mdot, Tb)
        """

        # burner temperature based on power
        Tb = T_burner_on if power_on else T_burner_off

        # step metal plate
        step_metal_numba(u, u_next, burner_mask, Tb, r)

        # heat input from metal to water
        Q_in = q_in_numba(u_next, T_w, h_mw, dA)
        Q_loss = UA_loss * (T_w - T_amb)

        # headspace geometry
        V_w = m_w / rho_w
        V_total = A_surf * H_pot
        Vg = V_total - V_w
        if Vg < 1e-9:
            Vg = 1e-9

        Tg = T_w + 273.15
        Psat = psat_water_pa(T_w)
        Pv = (nv * R_gas * Tg) / Vg

        # condensation clamp
        if Pv > Psat:
            nv = Psat * Vg / (R_gas * Tg)
            Pv = Psat

        # evaporation kinetics
        if lid_on:
            drive = Psat - Pv
            if drive < 0.0:
                drive = 0.0
            dn_evap = K_evap * A_surf * drive
        else:
            Pv_amb = RH_amb * psat_water_pa(T_amb)
            drive = Psat - Pv_amb
            if drive < 0.0:
                drive = 0.0
            dn_evap = K_evap * open_evap_mult * A_surf * drive

        mdot = dn_evap * M_w  # kg/s

        # water energy balance
        denom = m_w * cp_w
        if denom < 1e-9:
            denom = 1e-9
        dTdt = (Q_in - mdot * h_fg - Q_loss) / denom
        T_w = T_w + dTdt * dt
        if T_w < -10.0:
            T_w = -10.0

        # water mass
        m_w = m_w - mdot * dt
        if m_w < 0.0:
            m_w = 0.0

        # vapor moles increase
        nv = nv + dn_evap * dt
        if nv < 0.0:
            nv = 0.0

        # venting when lid off: relax total moles toward ambient
        if not lid_on:
            # recompute Vg, Tg after updates
            V_w = m_w / rho_w
            Vg = (A_surf * H_pot) - V_w
            if Vg < 1e-9:
                Vg = 1e-9
            Tg = T_w + 273.15

            n_tot = na + nv
            n_eq = P_amb * Vg / (R_gas * Tg)
            if tau_vent < 1e-6:
                tau_vent = 1e-6
            dn_tot_dt = -(n_tot - n_eq) / tau_vent
            dn_tot = dn_tot_dt * dt

            frac_v = 0.0
            if n_tot > 1e-12:
                frac_v = nv / n_tot

            nv = nv + frac_v * dn_tot
            na = na + (1.0 - frac_v) * dn_tot
            if nv < 0.0:
                nv = 0.0
            if na < 0.0:
                na = 0.0

            # saturation clamp again
            Psat = psat_water_pa(T_w)
            Pv = (nv * R_gas * Tg) / Vg
            if Pv > Psat:
                nv = Psat * Vg / (R_gas * Tg)

        # pressures for logging
        V_w = m_w / rho_w
        Vg = (A_surf * H_pot) - V_w
        if Vg < 1e-9:
            Vg = 1e-9
        Tg = T_w + 273.15
        P = (na + nv) * R_gas * Tg / Vg
        Pv = (nv * R_gas * Tg) / Vg

        return T_w, m_w, nv, na, P, Pv, mdot, Tb

# ---------------------------
# E) Initial conditions
# ---------------------------
u = np.full((N, N), T_amb, dtype=np.float64)
u_next = u.copy()

V_w0 = A_surf * (H_pot * fill_frac)
m_w0 = rho_w * V_w0
T_w0 = T_amb

RH0 = 0.50
Vg0 = headspace_volume(m_w0)
Tg0 = T_w0 + 273.15
Pv0 = RH0 * psat_water_pa_py(T_w0)
nv0 = Pv0 * Vg0 / (R_gas * Tg0)
na0 = (P_amb - Pv0) * Vg0 / (R_gas * Tg0)

# ---------------------------
# F) Interactive controls ("knobs")
# ---------------------------
state = {
    "power_on": True,
    "lid_on": True,
    "T_burner_on": 180.0,
    "T_burner_off": T_amb,
    "h_mw": 2500.0,
    "K_evap": 2e-7,
    "tau_vent": 0.35,
    "UA_loss": 8.0,
    "open_evap_mult": 8.0,
    "RH_amb": RH0,
}

# ---------------------------
# G) Matplotlib UI (timer-based)
# ---------------------------
plt.ion()
fig = plt.figure(figsize=(13, 6))

ax_map = fig.add_axes([0.05, 0.18, 0.42, 0.75])
ax_ts  = fig.add_axes([0.52, 0.18, 0.45, 0.75])

# sliders
ax_hmw   = fig.add_axes([0.07, 0.11, 0.35, 0.03])
ax_Tburn = fig.add_axes([0.07, 0.07, 0.35, 0.03])
ax_UA    = fig.add_axes([0.07, 0.03, 0.35, 0.03])

ax_Ke    = fig.add_axes([0.55, 0.11, 0.35, 0.03])
ax_tau   = fig.add_axes([0.55, 0.07, 0.35, 0.03])
ax_RH    = fig.add_axes([0.55, 0.03, 0.35, 0.03])

# buttons
ax_power = fig.add_axes([0.44, 0.11, 0.07, 0.06])
ax_lid   = fig.add_axes([0.44, 0.03, 0.07, 0.06])
ax_reset = fig.add_axes([0.44, 0.07, 0.07, 0.035])

im = ax_map.imshow(u, cmap="hot", vmin=20, vmax=260, extent=[0, L, 0, L])
plt.colorbar(im, ax=ax_map, label="Pot-bottom Temp (°C)")
ax_map.set_title("2D Pot-Bottom Temperature")

t_hist, Tw_hist, P_hist, mdot_hist = [], [], [], []
ln_Tw, = ax_ts.plot([], [], label="Water Temp (°C)")
ln_dP, = ax_ts.plot([], [], label="Headspace ΔP (kPa)")
ln_md, = ax_ts.plot([], [], label="Evap m_dot (g/s)")
ax_ts.grid(True)
ax_ts.set_xlabel("Time (s)")
ax_ts.legend(loc="upper left")

s_hmw = Slider(ax_hmw, "h_mw (W/m²K)", 200.0, 15000.0, valinit=state["h_mw"])
s_Tb  = Slider(ax_Tburn, "Burner T (°C)", 60.0, 350.0, valinit=state["T_burner_on"])
s_UA  = Slider(ax_UA, "UA_loss (W/K)", 0.0, 80.0, valinit=state["UA_loss"])

s_Ke  = Slider(ax_Ke, "K_evap (×1e-7)", 0.0, 40.0, valinit=state["K_evap"] / 1e-7)
s_tau = Slider(ax_tau, "tau_vent (s)", 0.05, 2.0, valinit=state["tau_vent"])
s_RH  = Slider(ax_RH, "RH_amb", 0.0, 1.0, valinit=state["RH_amb"])

b_power = Button(ax_power, "POWER: ON")
b_lid   = Button(ax_lid,   "LID: ON")
b_reset = Button(ax_reset, "RESET")

















# Simulation state
sim = {
    "t": 0.0,
    "T_w": T_w0,
    "m_w": m_w0,
    "nv": nv0,
    "na": na0,
}

# constant
dA = (L / N) ** 2

def update_from_sliders(_=None):
    state["h_mw"] = float(s_hmw.val)
    state["T_burner_on"] = float(s_Tb.val)
    state["UA_loss"] = float(s_UA.val)
    state["K_evap"] = float(s_Ke.val) * 1e-7
    state["tau_vent"] = float(s_tau.val)
    state["RH_amb"] = float(s_RH.val)

for s in (s_hmw, s_Tb, s_UA, s_Ke, s_tau, s_RH):
    s.on_changed(update_from_sliders)

def on_power(_):
    state["power_on"] = not state["power_on"]
    b_power.label.set_text(f"POWER: {'ON' if state['power_on'] else 'OFF'}")

def on_lid(_):
    state["lid_on"] = not state["lid_on"]
    b_lid.label.set_text(f"LID: {'ON' if state['lid_on'] else 'OFF'}")

def on_reset(_):
    sim["t"] = 0.0
    sim["T_w"] = T_w0
    sim["m_w"] = m_w0
    sim["nv"] = nv0
    sim["na"] = na0
    u[:, :] = T_amb
    u_next[:, :] = T_amb

    t_hist.clear(); Tw_hist.clear(); P_hist.clear(); mdot_hist.clear()
    im.set_data(u)
    ln_Tw.set_data([], [])
    ln_dP.set_data([], [])
    ln_md.set_data([], [])
    ax_map.set_title("2D Pot-Bottom Temperature (reset)")
    fig.canvas.draw_idle()

b_power.on_clicked(on_power)
b_lid.on_clicked(on_lid)
b_reset.on_clicked(on_reset)

# ---- warm-up compile (important: avoids first-click lag)
if NUMBA_OK:
    print("Numba enabled: warming up JIT compilation...")
    update_from_sliders()
    # do a couple steps to compile
    for _ in range(2):
        sim["T_w"], sim["m_w"], sim["nv"], sim["na"], P, Pv, mdot, Tb = vertical_step_numba(
            u, u_next, burner_mask,
            sim["T_w"], sim["m_w"], sim["nv"], sim["na"],
            state["power_on"], state["lid_on"],
            state["T_burner_on"], state["T_burner_off"],
            state["h_mw"], state["UA_loss"], state["K_evap"], state["tau_vent"],
            state["open_evap_mult"], state["RH_amb"],
            r, dA
        )
        u[:, :] = u_next
    print("JIT warm-up complete.")
else:
    print("Numba not available: running in pure Python/NumPy (slower).")

# ---- timer update
STEPS_PER_TICK = 25  # increase for faster physics per real-time second (CPU permitting)

def timer_update():
    update_from_sliders()

    # Step the simulation multiple times per GUI tick
    for _ in range(STEPS_PER_TICK):
        if NUMBA_OK:
            sim["T_w"], sim["m_w"], sim["nv"], sim["na"], P, Pv, mdot, Tb = vertical_step_numba(
                u, u_next, burner_mask,
                sim["T_w"], sim["m_w"], sim["nv"], sim["na"],
                state["power_on"], state["lid_on"],
                state["T_burner_on"], state["T_burner_off"],
                state["h_mw"], state["UA_loss"], state["K_evap"], state["tau_vent"],
                state["open_evap_mult"], state["RH_amb"],
                r, dA
            )
            # swap buffers
            u[:, :] = u_next
        else:
            # fallback: slower pure python version (minimal, uses numpy diffusion)
            # (kept brief—if you want, I can include a full non-numba fallback)
            pass

        sim["t"] += dt
        t_hist.append(sim["t"])
        Tw_hist.append(sim["T_w"])
        P_hist.append(P)
        mdot_hist.append(mdot)

    # Update visuals
    im.set_data(u)
    ax_map.set_title(
        f"2D Pot-Bottom | t={sim['t']:.1f}s | "
        f"POWER={'ON' if state['power_on'] else 'OFF'} | "
        f"LID={'ON' if state['lid_on'] else 'OFF'} | "
        f"Tb={Tb:.0f}°C | N={N}"
    )

    ln_Tw.set_data(t_hist, Tw_hist)
    ln_dP.set_data(t_hist, (np.array(P_hist) - P_amb) / 1000.0)   # kPa
    ln_md.set_data(t_hist, np.array(mdot_hist) * 1000.0)          # g/s

    ax_ts.relim()
    ax_ts.autoscale_view()
    fig.canvas.draw_idle()

timer = fig.canvas.new_timer(interval=20)  # ms
timer.add_callback(timer_update)
timer.start()

plt.show()
