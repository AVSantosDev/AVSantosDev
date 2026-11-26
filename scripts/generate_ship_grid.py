import json
import os
import urllib.request
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "AVSantosDev")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_PATH = Path("dist/github-contribution-grid-snake-dark.svg")

# Cores dark padrão do GitHub por nível (0 a 4)
LEVEL_COLORS = {
    0: "#161b22",
    1: "#0e4429",
    2: "#006d32",
    3: "#26a641",
    4: "#39d353",
}


def fetch_contribution_grid(username: str, token: str) -> list[list[int]]:
    """Retorna uma matriz [7 linhas (dias da semana)][N colunas (semanas)] com níveis 0..4."""
    if token:
        query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                weeks {
                  contributionDays {
                    contributionLevel
                  }
                }
              }
            }
          }
        }
        """
        level_map = {
            "NONE": 0,
            "FIRST_QUARTILE": 1,
            "SECOND_QUARTILE": 2,
            "THIRD_QUARTILE": 3,
            "FOURTH_QUARTILE": 4,
        }
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "ship-grid-generator",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                cols = len(weeks)
                grid = [[0 for _ in range(cols)] for _ in range(7)]
                for c_idx, week in enumerate(weeks):
                    for d_idx, day in enumerate(week["contributionDays"]):
                        if d_idx < 7:
                            grid[d_idx][c_idx] = level_map.get(day["contributionLevel"], 0)
                return grid
        except Exception as exc:
            print(f"Aviso: falha na API GraphQL ({exc}), usando grade de exemplo.")

    # Fallback caso rode localmente sem token
    cols = 53
    grid = [[0 for _ in range(cols)] for _ in range(7)]
    for c in range(cols):
        for r in range(7):
            if (c + r * 3) % 7 == 0:
                grid[r][c] = 2
            elif (c * 2 + r) % 11 == 0:
                grid[r][c] = 4
    return grid


def pick_targets_across_grid(grid: list[list[int]], max_targets: int = 55) -> list[tuple[int, int, int]]:
    """Seleciona alvos com contribuições distribuídos da esquerda até a última coluna da direita."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 53

    # Coleta o melhor alvo por coluna (ou vários ao longo de todas as colunas)
    per_col: list[tuple[int, int, int]] = []
    for c in range(cols):
        col_cells = [(r, c, grid[r][c]) for r in range(rows) if grid[r][c] > 0]
        if col_cells:
            # Escolhe uma célula com contribuição nessa coluna
            chosen = col_cells[c % len(col_cells)]
            per_col.append(chosen)

    if len(per_col) <= max_targets:
        return per_col

    # Amostragem uniforme incluindo sempre o primeiro e o último alvo da direita
    step = (len(per_col) - 1) / (max_targets - 1)
    indices = sorted({round(i * step) for i in range(max_targets)})
    return [per_col[i] for i in indices]


def build_svg(grid: list[list[int]]) -> str:
    rows = len(grid)
    cols = len(grid[0]) if rows else 53

    cell = 11
    gap = 3
    step = cell + gap
    pad_x = 16
    pad_y = 14
    ship_lane_height = 34

    grid_w = cols * step - gap
    grid_h = rows * step - gap
    width = pad_x * 2 + grid_w
    height = pad_y * 2 + grid_h + ship_lane_height

    targets = pick_targets_across_grid(grid, max_targets=53)
    n = max(1, len(targets))

    # Cada passo tem: movimento/alinhamento + disparo + destruição
    step_dur = 0.22
    travel_dur = 0.09
    shot_dur = 0.08
    # Tempo total inclui ida até o fim e retorno suave ao início
    total_dur = round(n * step_dur + 1.4, 2)

    start_x = pad_x + (cols - 1) * step + cell / 2 - 10
    first_x = pad_x + cell / 2 - 10
    ship_y = pad_y + grid_h + 12

    target_map: dict[tuple[int, int], dict] = {}
    shots_svg = []
    hit_flashes_svg = []

    ship_times = ["0.0000"]
    ship_xs = [f"{first_x:.1f}"]

    for idx, (r, c, level) in enumerate(targets):
        bx = pad_x + c * step
        by = pad_y + r * step
        target_center_x = bx + cell / 2 - 10

        t_arrive = idx * step_dur + travel_dur
        t_hit = min(total_dur - 0.3, t_arrive + shot_dur)
        t_respawn = min(total_dur - 0.15, t_hit + 1.6)

        ship_times.append(f"{min(0.96, t_arrive / total_dur):.4f}")
        ship_xs.append(f"{target_center_x:.1f}")

        # Guarda dados de destruição caso a mesma célula apareça mais de uma vez
        key = (r, c)
        if key not in target_map:
            target_map[key] = {
                "level": level,
                "t_hit": t_hit,
                "t_respawn": t_respawn,
            }

        # Projétil parte da nave já alinhada e sobe até ao bloco
        shot_x = bx + cell / 2 - 1.5
        shot_y_start = ship_y - 4
        shot_y_end = by + cell / 2

        shots_svg.append(
            f'<rect x="{shot_x:.1f}" y="{shot_y_end:.1f}" width="3" height="9" rx="1.5" fill="#38bdf8" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.15;0.85;1" '
            f'dur="{shot_dur:.2f}s" begin="{t_arrive:.2f}s" repeatCount="indefinite" />'
            f'<animate attributeName="y" from="{shot_y_start:.1f}" to="{shot_y_end:.1f}" '
            f'dur="{shot_dur:.2f}s" begin="{t_arrive:.2f}s" repeatCount="indefinite" />'
            f'</rect>'
        )

        # Flash rápido no ponto de impacto
        flash_cx = bx + cell / 2
        flash_cy = by + cell / 2
        hit_flashes_svg.append(
            f'<circle cx="{flash_cx:.1f}" cy="{flash_cy:.1f}" r="2" fill="#e0f2fe" opacity="0">'
            f'<animate attributeName="opacity" values="0;0.95;0" keyTimes="0;0.3;1" '
            f'dur="0.16s" begin="{t_hit:.2f}s" repeatCount="indefinite" />'
            f'<animate attributeName="r" values="2;7;1" keyTimes="0;0.5;1" '
            f'dur="0.16s" begin="{t_hit:.2f}s" repeatCount="indefinite" />'
            f'</circle>'
        )

    # Garante que a nave chega até a última coluna à direita e depois regressa ao início
    last_bx = pad_x + (cols - 1) * step
    last_ship_x = last_bx + cell / 2 - 10
    ship_times.extend(["0.9600", "1.0000"])
    ship_xs.extend([f"{last_ship_x:.1f}", f"{first_x:.1f}"])

    blocks_svg = []
    for r in range(rows):
        for c in range(cols):
            level = grid[r][c]
            if level <= 0:
                continue

            bx = pad_x + c * step
            by = pad_y + r * step
            cx = bx + cell / 2
            cy = by + cell / 2
            color = LEVEL_COLORS.get(level, "#26a641")

            info = target_map.get((r, c))
            if info:
                t_hit = info["t_hit"]
                t_respawn = info["t_respawn"]
                kt1 = max(0.001, min(0.92, t_hit / total_dur))
                kt2 = max(kt1 + 0.002, min(0.94, (t_hit + 0.05) / total_dur))
                kt3 = max(kt2 + 0.002, min(0.98, t_respawn / total_dur))

                key_times = f"0;{kt1:.4f};{kt2:.4f};{kt3:.4f};1"
                scale_vals = "1;1;0.05;0.05;1"
                op_vals = "1;1;0;0;1"

                blocks_svg.append(
                    f'<g transform="translate({cx:.1f} {cy:.1f})">'
                    f'<rect x="{-cell/2:.1f}" y="{-cell/2:.1f}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
                    f'<animate attributeName="opacity" values="{op_vals}" keyTimes="{key_times}" '
                    f'dur="{total_dur:.2f}s" repeatCount="indefinite" />'
                    f'</rect>'
                    f'<animateTransform attributeName="transform" additive="sum" type="scale" '
                    f'values="{scale_vals}" keyTimes="{key_times}" dur="{total_dur:.2f}s" repeatCount="indefinite" />'
                    f'</g>'
                )
            else:
                blocks_svg.append(
                    f'<rect x="{bx}" y="{by}" width="{cell}" height="{cell}" rx="2" fill="{color}" />'
                )

    bg_cells = [
        f'<rect x="{pad_x + c * step}" y="{pad_y + r * step}" width="{cell}" height="{cell}" rx="2" fill="{LEVEL_COLORS[0]}" />'
        for c in range(cols)
        for r in range(rows)
        if grid[r][c] == 0
    ]

    ship_group = (
        f'<g transform="translate(0 {ship_y:.1f})">'
        f'<animateTransform attributeName="transform" additive="sum" type="translate" '
        f'values="{";".join(ship_xs)}" keyTimes="{";".join(ship_times)}" '
        f'dur="{total_dur:.2f}s" repeatCount="indefinite" />'
        f'<polygon points="10,0 18,10 13,10 13,12 7,12 7,10 2,10" fill="#38bdf8" />'
        f'<rect x="9" y="3" width="2" height="4" fill="#e0f2fe" />'
        f'</g>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <rect width="{width}" height="{height}" rx="6" fill="#0d1117" />
  <g id="empty-grid">
    {"".join(bg_cells)}
  </g>
  <g id="targets">
    {"".join(blocks_svg)}
  </g>
  <g id="flashes">
    {"".join(hit_flashes_svg)}
  </g>
  <g id="shots">
    {"".join(shots_svg)}
  </g>
  <g id="ship">
    {ship_group}
  </g>
</svg>
"""


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    grid = fetch_contribution_grid(USERNAME, TOKEN)
    svg = build_svg(grid)
    OUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Gerado com sucesso: {OUT_PATH}")


if __name__ == "__main__":
    main()
