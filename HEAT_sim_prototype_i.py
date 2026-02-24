import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import matplotlib.patches as patches
from matplotlib.patheffects import withStroke

# If you're in Jupyter, you can uncomment this:
%matplotlib tk

# Optional speedup (Numba)
try:
    from numba import njit, prange
    NUMBA_OK = True
except Exception:
    NUMBA_OK = False
    njit = None
    prange = range


# ============================================================
# Portable Electric Stove Theme (FULL, CORRECTED)
# ============================================================
def apply_stove_theme(
    fig,
    ax_map,
    ax_ts,
    slider_axes,
    button_axes,
    b_power=None,
    b_lid=None,
    b_reset=None,
    state=None,
    get_readouts=None,
):
    """
    Portable electric stove theme + control layout polish.

    Adds:
    - dark "stove body" + rounded frame
    - glass cooktop panel + control deck panel
    - group labels (HEAT / EVAP / VENT / AMBIENT)
    - button styling + LEDs (POWER/LID/BOIL)
    - readout strip (Water Temp / ΔP / Evap)
    - fig._stove_readout_update() hook for timer/callback refresh
    """

    # ------------- helpers -------------
    def _as_dict(maybe_dict, fallback_names):
        if isinstance(maybe_dict, dict):
            return maybe_dict
        if isinstance(maybe_dict, (list, tuple)):
            d = {}
            for i, ax in enumerate(maybe_dict):
                name = fallback_names[i] if i < len(fallback_names) else f"ax{i}"
                d[name] = ax
            return d
        return {}

    def _wipe_old_theme(_fig):
        # Remove previously tagged stove patches/texts
        _fig.patches = [p for p in _fig.patches if not getattr(p, "_stove_ui", False)]
        _fig.texts = [t for t in _fig.texts if not getattr(t, "_stove_ui", False)]

    def _add_patch(p):
        p._stove_ui = True
        fig.patches.append(p)

    def _add_text(*args, **kwargs):
        t = fig.text(*args, **kwargs)
        t._stove_ui = True
        return t

    def _style_plot_axes(ax):
        ax.set_facecolor("#15181b")
        for spine in ax.spines.values():
            spine.set_color("#3a3f45")
            spine.set_linewidth(1.2)
        ax.tick_params(colors="#cfd6dd", labelsize=9)
        ax.title.set_color("#e7edf5")
        ax.xaxis.label.set_color("#cfd6dd")
        ax.yaxis.label.set_color("#cfd6dd")
        ax.grid(True, alpha=0.15)

    def _style_inset_axes(ax):
        ax.set_facecolor("#0b0d0f")
        for spine in ax.spines.values():
            spine.set_color("#22272d")
            spine.set_linewidth(1.0)
        ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
        # subtle top highlight
        ax.plot([0, 1], [1, 1], transform=ax.transAxes, color="#2a3036", lw=1, alpha=0.8)

    def _style_button(btn, face="#2b2f36", hover="#3a424d"):
        if btn is None:
            return
        try:
            btn.ax.set_facecolor(face)
            btn.color = face
            btn.hovercolor = hover
        except Exception:
            pass
        btn.label.set_color("#e7edf5")
        btn.label.set_fontsize(9)
        btn.label.set_fontweight("bold")

    def _set_button_led(btn, on, kind="power"):
        if btn is None:
            return
        if kind == "power":
            face = "#173a2a" if on else "#2a2f36"
            hover = "#2b5a3e" if on else "#3a424d"
            label = f"POWER: {'ON' if on else 'OFF'}"
        elif kind == "lid":
            face = "#3a2a17" if on else "#2a2f36"
            hover = "#6a4b24" if on else "#3a424d"
            label = f"LID: {'ON' if on else 'OFF'}"
        else:
            face = "#2a2f36"
            hover = "#3a424d"
            label = btn.label.get_text()

        try:
            btn.ax.set_facecolor(face)
            btn.color = face
            btn.hovercolor = hover
        except Exception:
            pass
        btn.label.set_text(label)
        btn.label.set_color("#e7edf5")
        btn.label.set_fontweight("bold")

    def _add_led(x, y, on_color, label=None):
        led = patches.Circle(
            (x, y), 0.0078,
            transform=fig.transFigure,
            facecolor="#1b1f23",
            edgecolor="#2f343b",
            linewidth=1.0,
            zorder=50
        )
        led._stove_ui = True
        fig.patches.append(led)

        if label is not None:
            _add_text(
                x + 0.012, y - 0.006, label,
                color="#9aa6b2", fontsize=8,
                path_effects=[withStroke(linewidth=2, foreground="#0b0d0f")]
            )

        def set_state(on):
            led.set_facecolor(on_color if on else "#1b1f23")

        return set_state

    # ------------- apply theme -------------
    _wipe_old_theme(fig)

    fig.patch.set_facecolor("#101214")
    _style_plot_axes(ax_map)
    _style_plot_axes(ax_ts)

    slider_axes = _as_dict(slider_axes, ["hmw", "Tb", "UA", "Ke", "tau", "RH"])
    button_axes = _as_dict(button_axes, ["power", "reset", "lid"])

    for ax in slider_axes.values():
        _style_inset_axes(ax)
    for ax in button_axes.values():
        _style_inset_axes(ax)

    # Stove frame + panels
    frame = patches.FancyBboxPatch(
        (0.01, 0.01), 0.98, 0.98,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        transform=fig.transFigure,
        linewidth=2.0,
        edgecolor="#2b3036",
        facecolor="#0f1113",
        zorder=-10
    )
    _add_patch(frame)

    cooktop = patches.FancyBboxPatch(
        (0.03, 0.16), 0.94, 0.80,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        transform=fig.transFigure,
        linewidth=1.5,
        edgecolor="#2f343b",
        facecolor="#121518",
        zorder=-9
    )
    _add_patch(cooktop)

    control = patches.FancyBboxPatch(
        (0.03, 0.02), 0.94, 0.12,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        transform=fig.transFigure,
        linewidth=1.5,
        edgecolor="#2f343b",
        facecolor="#0d0f11",
        zorder=-9
    )
    _add_patch(control)

    div = patches.FancyBboxPatch(
        (0.03, 0.155), 0.94, 0.002,
        boxstyle="round,pad=0.0,rounding_size=0.004",
        transform=fig.transFigure,
        linewidth=0,
        facecolor="#232931",
        zorder=-8,
        alpha=0.8
    )
    _add_patch(div)

    # Header
    _add_text(
        0.04, 0.945, "PORTABLE ELECTRIC STOVE SIM",
        color="#e7edf5", fontsize=10, fontweight="bold",
        path_effects=[withStroke(linewidth=3, foreground="#0b0d0f")]
    )
    _add_text(
        0.04, 0.920, "2D Cooktop • 1D Pot/Headspace • Interactive",
        color="#9aa6b2", fontsize=8
    )

    # Group labels
    _add_text(0.04, 0.137, "HEAT", color="#cfd6dd", fontsize=8, fontweight="bold",
              path_effects=[withStroke(linewidth=2, foreground="#0b0d0f")])
    _add_text(0.04, 0.113, "POT COUPLING", color="#9aa6b2", fontsize=7)

    _add_text(0.53, 0.137, "EVAP / VENT", color="#cfd6dd", fontsize=8, fontweight="bold",
              path_effects=[withStroke(linewidth=2, foreground="#0b0d0f")])
    _add_text(0.53, 0.113, "AMBIENT / HEADSPACE", color="#9aa6b2", fontsize=7)

    # Buttons
    _style_button(b_power)
    _style_button(b_lid)
    _style_button(b_reset, face="#2b2f36", hover="#444d58")

    # LEDs
    set_power_led = _add_led(0.468, 0.132, on_color="#21d07a", label="POWER")
    set_lid_led   = _add_led(0.468, 0.050, on_color="#ffb020", label="LID")
    set_boil_led  = _add_led(0.92,  0.132, on_color="#ff3b3b", label="BOIL")

    # Readout strip# --- Readout strip (moved into header, not over plots)
    readout_box = patches.FancyBboxPatch(
    (0.52, 0.935), 0.45, 0.045,   # x, y, w, h  (header zone)
    boxstyle="round,pad=0.010,rounding_size=0.015",
    transform=fig.transFigure,
    linewidth=1.2,
    edgecolor="#2f343b",
    facecolor="#0b0d0f",
    zorder=60
    )

        
        # labels
    _add_text(0.535, 0.965, "WATER", color="#9aa6b2", fontsize=7)
    _add_text(0.690, 0.965, "ΔP",    color="#9aa6b2", fontsize=7)
    _add_text(0.785, 0.965, "EVAP",  color="#9aa6b2", fontsize=7)
    
    # numbers
    t_Tw = _add_text(0.535, 0.942, "--.-°C",  color="#e7edf5", fontsize=11, fontweight="bold",
                     path_effects=[withStroke(linewidth=3, foreground="#050607")])
    t_dP = _add_text(0.675, 0.942, "--.-kPa", color="#e7edf5", fontsize=11, fontweight="bold",
                     path_effects=[withStroke(linewidth=3, foreground="#050607")])
    t_md = _add_text(0.765, 0.942, "--.-g/s", color="#e7edf5", fontsize=11, fontweight="bold",
                     path_effects=[withStroke(linewidth=3, foreground="#050607")])

    # Public updater hook
    def _update_readouts():
        # buttons + LEDs from state
        if state is not None:
            p_on = bool(state.get("power_on", True))
            l_on = bool(state.get("lid_on", True))
            set_power_led(p_on)
            set_lid_led(l_on)
            _set_button_led(b_power, p_on, kind="power")
            _set_button_led(b_lid, l_on, kind="lid")

        if get_readouts is None:
            return

        r = get_readouts() or {}
        Tw = r.get("Tw", None)
        dP = r.get("dP_kPa", None)
        md = r.get("mdot_gs", None)

        if Tw is not None:
            t_Tw.set_text(f"{Tw:4.1f}°C")
            set_boil_led(Tw >= 99.0)
        if dP is not None:
            t_dP.set_text(f"{dP:4.1f}kPa")
        if md is not None:
            t_md.set_text(f"{md:4.2f}g/s")

    fig._stove_readout_update = _update_readouts
    _update_readouts()

    # optional: hide toolbar if backend supports it
    try:
        plt.rcParams["toolbar"] = "None"
    except Exception:
        pass


# ============================================================
# Physics / Sim Setup
# ============================================================

# --- 2D metal plate
L = 0.20
N = 120
dx = L / N
dt = 0.01

alpha_steel = 4.2e-6
r = alpha_steel * dt / dx**2
print(f"2D explicit stability r = {r:.4f} (want <= ~0.25)")

center = N // 2
radius = N // 4
Y, X = np.ogrid[:N, :N]
burner_mask = ((X - center)**2 + (Y - center)**2 <= radius**2).astype(np.uint8)

# --- pot / water / headspace constants
R_pot = 0.10
H_pot = 0.12
A_surf = np.pi * R_pot**2

fill_frac = 1/3
rho_w = 997.0
cp_w = 4180.0

T_amb = 20.0
P_amb = 101325.0
R_gas = 8.314462618
M_w = 0.01801528
h_fg = 2.256e6

def headspace_volume(m_w):
    V_w = m_w / rho_w
    V_total = A_surf * H_pot
    return max(V_total - V_w, 1e-9)

def psat_water_pa_py(Tc):
    A = 8.07131
    B = 1730.63
    C = 233.426
    P_mmHg = 10 ** (A - B / (C + Tc))
    return P_mmHg * 133.322368

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


# --- Numba hot path
if NUMBA_OK:
    @njit(parallel=True, fastmath=True)
    def step_metal_numba(u, u_next, burner_mask, T_burner, r):
        n = u.shape[0]
        for i in prange(1, n - 1):
            for j in range(1, n - 1):
                lap = (u[i+1, j] + u[i-1, j] + u[i, j+1] + u[i, j-1] - 4.0 * u[i, j])
                u_next[i, j] = u[i, j] + r * lap

        for j in prange(n):
            u_next[0, j] = u_next[1, j]
            u_next[n-1, j] = u_next[n-2, j]
        for i in prange(n):
            u_next[i, 0] = u_next[i, 1]
            u_next[i, n-1] = u_next[i, n-2]

        for i in prange(n):
            for j in range(n):
                if burner_mask[i, j] == 1:
                    u_next[i, j] = T_burner

    @njit(parallel=True, fastmath=True)
    def q_in_numba(u, T_w, h_mw, dA):
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

        Tb = T_burner_on if power_on else T_burner_off
        step_metal_numba(u, u_next, burner_mask, Tb, r)

        Q_in = q_in_numba(u_next, T_w, h_mw, dA)
        Q_loss = UA_loss * (T_w - T_amb)

        V_w = m_w / rho_w
        V_total = A_surf * H_pot
        Vg = V_total - V_w
        if Vg < 1e-9:
            Vg = 1e-9

        Tg = T_w + 273.15
        Psat = psat_water_pa(T_w)
        Pv = (nv * R_gas * Tg) / Vg

        if Pv > Psat:
            nv = Psat * Vg / (R_gas * Tg)
            Pv = Psat

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

        mdot = dn_evap * M_w

        denom = m_w * cp_w
        if denom < 1e-9:
            denom = 1e-9
        dTdt = (Q_in - mdot * h_fg - Q_loss) / denom
        T_w = T_w + dTdt * dt
        if T_w < -10.0:
            T_w = -10.0

        m_w = m_w - mdot * dt
        if m_w < 0.0:
            m_w = 0.0

        nv = nv + dn_evap * dt
        if nv < 0.0:
            nv = 0.0

        if not lid_on:
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

            Psat = psat_water_pa(T_w)
            Pv = (nv * R_gas * Tg) / Vg
            if Pv > Psat:
                nv = Psat * Vg / (R_gas * Tg)

        V_w = m_w / rho_w
        Vg = (A_surf * H_pot) - V_w
        if Vg < 1e-9:
            Vg = 1e-9
        Tg = T_w + 273.15
        P = (na + nv) * R_gas * Tg / Vg
        Pv = (nv * R_gas * Tg) / Vg

        return T_w, m_w, nv, na, P, Pv, mdot, Tb


# ============================================================
# Initial Conditions
# ============================================================
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


# ============================================================
# UI State
# ============================================================
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


# ============================================================
# Matplotlib UI
# ============================================================
plt.ion()
fig = plt.figure(figsize=(13, 6))

ax_map = fig.add_axes([0.05, 0.18, 0.42, 0.75])
ax_ts  = fig.add_axes([0.52, 0.18, 0.45, 0.75])

# Sliders
ax_hmw   = fig.add_axes([0.07, 0.11, 0.35, 0.03])
ax_Tburn = fig.add_axes([0.07, 0.07, 0.35, 0.03])
ax_UA    = fig.add_axes([0.07, 0.03, 0.35, 0.03])

ax_Ke    = fig.add_axes([0.55, 0.11, 0.35, 0.03])
ax_tau   = fig.add_axes([0.55, 0.07, 0.35, 0.03])
ax_RH    = fig.add_axes([0.55, 0.03, 0.35, 0.03])

# Buttons
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

b_power = Button(ax_power, "POWER")
b_lid   = Button(ax_lid,   "LID")
b_reset = Button(ax_reset, "RESET")


# ============================================================
# Simulation State (IMPORTANT: define BEFORE theming readouts)
# ============================================================
sim = {
    "t": 0.0,
    "T_w": T_w0,
    "m_w": m_w0,
    "nv": nv0,
    "na": na0,
}

# Safe initial readout values (so theme doesn't reference undefined vars)
P = P_amb
mdot = 0.0
Tb = state["T_burner_on"] if state["power_on"] else state["T_burner_off"]

# constant
dA = (L / N) ** 2


# ============================================================
# Apply Stove Theme (NOW it's safe)
# ============================================================
apply_stove_theme(
    fig,
    ax_map,
    ax_ts,
    slider_axes={"hmw": ax_hmw, "Tb": ax_Tburn, "UA": ax_UA, "Ke": ax_Ke, "tau": ax_tau, "RH": ax_RH},
    button_axes={"power": ax_power, "reset": ax_reset, "lid": ax_lid},
    b_power=b_power, b_lid=b_lid, b_reset=b_reset,
    state=state,
    get_readouts=lambda: {
        "Tw": sim["T_w"],
        "dP_kPa": (P - P_amb) / 1000.0,
        "mdot_gs": mdot * 1000.0
    }
)


# ============================================================
# Slider + Button callbacks
# ============================================================
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
    if hasattr(fig, "_stove_readout_update"):
        fig._stove_readout_update()
    fig.canvas.draw_idle()

def on_lid(_):
    state["lid_on"] = not state["lid_on"]
    if hasattr(fig, "_stove_readout_update"):
        fig._stove_readout_update()
    fig.canvas.draw_idle()

def on_reset(_):
    global P, mdot, Tb
    sim["t"] = 0.0
    sim["T_w"] = T_w0
    sim["m_w"] = m_w0
    sim["nv"] = nv0
    sim["na"] = na0

    P = P_amb
    mdot = 0.0
    Tb = state["T_burner_on"] if state["power_on"] else state["T_burner_off"]

    u[:, :] = T_amb
    u_next[:, :] = T_amb

    t_hist.clear(); Tw_hist.clear(); P_hist.clear(); mdot_hist.clear()
    im.set_data(u)
    ln_Tw.set_data([], [])
    ln_dP.set_data([], [])
    ln_md.set_data([], [])

    ax_map.set_title("2D Pot-Bottom Temperature (reset)")
    if hasattr(fig, "_stove_readout_update"):
        fig._stove_readout_update()
    fig.canvas.draw_idle()

b_power.on_clicked(on_power)
b_lid.on_clicked(on_lid)
b_reset.on_clicked(on_reset)


# ============================================================
# Warm-up compile (optional, avoids first-click lag)
# ============================================================
if NUMBA_OK:
    print("Numba enabled: warming up JIT compilation...")
    update_from_sliders()
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


# ============================================================
# Timer update
# ============================================================
STEPS_PER_TICK = 25  # increase for faster sim-time per wall-time

def timer_update():
    global P, mdot, Tb

    update_from_sliders()

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
            u[:, :] = u_next
        else:
            # (optional) You can add a pure-NumPy fallback here if needed.
            pass

        sim["t"] += dt
        t_hist.append(sim["t"])
        Tw_hist.append(sim["T_w"])
        P_hist.append(P)
        mdot_hist.append(mdot)

    # Update readout strip + LEDs + button states
    if hasattr(fig, "_stove_readout_update"):
        fig._stove_readout_update()

    # Visual updates
    im.set_data(u)
    ax_map.set_title(
        f"2D Pot-Bottom | t={sim['t']:.1f}s | "
        f"POWER={'ON' if state['power_on'] else 'OFF'} | "
        f"LID={'ON' if state['lid_on'] else 'OFF'} | "
        f"Tb={Tb:.0f}°C | N={N}"
    )

    ln_Tw.set_data(t_hist, Tw_hist)
    ln_dP.set_data(t_hist, (np.array(P_hist) - P_amb) / 1000.0)  # kPa
    ln_md.set_data(t_hist, np.array(mdot_hist) * 1000.0)         # g/s

    ax_ts.relim()
    ax_ts.autoscale_view()
    fig.canvas.draw_idle()

timer = fig.canvas.new_timer(interval=20)  # ms
timer.add_callback(timer_update)
timer.start()

plt.show()
