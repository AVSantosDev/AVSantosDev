import json
import os
import urllib.request
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "AVSantosDev")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_PATH = Path("dist/github-contribution-grid-snake-dark.svg")

EMPTY_COLOR = "#161b22"
BG_COLOR = "#0d1117"
SHIP_COLOR = "#38bdf8"
LASER_COLOR = "#7dd3fc"

LEVEL_COLORS = {
    0: EMPTY_COLOR,
    1: "#0e4429",
    2: "#006d32",
    3: "#26a641",
    4: "#39d353",
}


def fetch_contribution_grid(username: str, token: str) -> list[list[int]]:
    """Retorna matriz [7 linhas (Dom..Sáb)][N colunas (semanas)] com níveis 0..4."""
    if token:
        query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                weeks {
                  contributionDays {
                    contributionLevel
                    weekday
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
                    for day in week["contributionDays"]:
                        wd = day.get("weekday", 0)
                        if 0 <= wd < 7:
                            grid[wd][c_idx] = level_map.get(day["contributionLevel"], 0)
                return grid
        except Exception as exc:
            print(f"Aviso: falha na API GraphQL ({exc}), usando grade de exemplo.")

    cols = 53
    grid = [[0 for _ in range(cols)] for _ in range(7)]
    for c in range(cols):
        for r in range(7):
            if (c + r * 3) % 6 == 0:
                grid[r][c] = 2
            elif (c * 2 + r) % 9 == 0:
                grid[r][c] = 3
    return grid


def strictly_increasing_times(raw_times: list[float]) -> list[str]:
    """Garante que keyTimes comecem em 0.0, terminem em 1.0 e sejam estritamente crescentes."""
    if not raw_times:
        return ["0.0000", "1.0000"]

    eps = 0.0002
    cleaned: list[float] = [0.0]
    for t in raw_times[1:-1]:
        clamped = max(cleaned[-1] + eps, min(1.0 - eps * 2, round(t, 4)))
        cleaned.append(clamped)

    cleaned.append(max(cleaned[-1] + eps, 1.0))
    # Se ultrapassou 1.0 por excesso de pontos, normaliza proporcionalmente
    if cleaned[-1] > 1.0:
        max_v = cleaned[-1]
        cleaned = [round(v / max_v, 4) for v in cleaned]
        cleaned[0] = 0.0
        cleaned[-1] = 1.0

    return [f"{v:.4f}" for v in cleaned]


def build_two_way_targets(grid: list[list[int]]) -> list[tuple[int, int, int]]:
    """
    Monta a fila de alvos em duas passadas:
    - Ida (esquerda -> direita): 1 alvo por coluna com contribuição
    - Volta (direita -> esquerda): blocos restantes que ficaram para trás
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 53

    pass1: list[tuple[int, int, int]] = []
    chosen_coords: set[tuple[int, int]] = set()

    for c in range(cols):
        col_hits = [(r, c, grid[r][c]) for r in range(rows) if grid[r][c] > 0]
        if col_hits:
            r, c_hit, lvl = col_hits[c % len(col_hits)]
            pass1.append((r, c_hit, lvl))
            chosen_coords.add((r, c_hit))

    remaining: list[tuple[int, int, int]] = []
    for c in range(cols - 1, -1, -1):
        for r in range(rows - 1, -1, -1):
            if grid[r][c] > 0 and (r, c) not in chosen_coords:
                remaining.append((r, c, grid[r][c]))

    return pass1 + remaining[:45]


def build_svg(grid: list[list[int]]) -> str:
    rows = 7
    cols = len(grid[0]) if grid and grid[0] else 53

    cell = 11
    gap = 3
    step = cell + gap
    pad_x = 16
    pad_y = 14
    ship_lane = 32

    grid_w = cols * step - gap
    grid_h = rows * step - gap
    width = pad_x * 2 + grid_w
    height = pad_y * 2 + grid_h + ship_lane

    targets = build_two_way_targets(grid)

    ship_y = pad_y + grid_h + 12
    first_x = pad_x + cell / 2 - 10

    dt_move = 0.12
    dt_shot = 0.07
    current_t = 0.15

    events = []
    hit_times: dict[tuple[int, int], float] = {}

    for r, c, _ in targets:
        bx = pad_x + c * step
        by = pad_y + r * step
        cx = bx + cell / 2
        cy = by + cell / 2
        ship_x = cx - 10

        t_arrive = round(current_t + dt_move, 3)
        t_hit = round(t_arrive + dt_shot, 3)
        events.append((r, c, bx, by, cx, cy, ship_x, t_arrive, t_hit))

        if (r, c) not in hit_times:
            hit_times[(r, c)] = t_hit

        current_t = t_hit + 0.02

    reset_pause = 0.9
    total_dur = round(max(1.5, current_t + reset_pause), 3)
    t_reset = round(max(0.2, total_dur - 0.15), 3)

    all_cells_svg = []
    for r in range(rows):
        for c in range(cols):
            level = grid[r][c]
            bx = pad_x + c * step
            by = pad_y + r * step
            color = LEVEL_COLORS.get(level, EMPTY_COLOR)

            if level > 0 and (r, c) in hit_times:
                t_hit = hit_times[(r, c)]
                t_after = round(t_hit + 0.03, 3)
                kt_list = strictly_increasing_times([
                    0.0,
                    t_hit / total_dur,
                    t_after / total_dur,
                    t_reset / total_dur,
                    1.0,
                ])
                all_cells_svg.append(
                    f'<rect x="{bx}" y="{by}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
                    f'<animate attributeName="opacity" values="1;1;0;0;1" '
                    f'keyTimes="{";".join(kt_list)}" '
                    f'dur="{total_dur}s" repeatCount="indefinite" />'
                    f'</rect>'
                )
            else:
                all_cells_svg.append(
                    f'<rect x="{bx}" y="{by}" width="{cell}" height="{cell}" rx="2" fill="{color}" />'
                )

    raw_ship_times = [0.0] + [t_arrive / total_dur for _, _, _, _, _, _, _, t_arrive, _ in events] + [
        t_reset / total_dur,
        1.0,
    ]
    ship_kt = strictly_increasing_times(raw_ship_times)
    ship_val = [f"{first_x:.1f}"] + [f"{ship_x:.1f}" for _, _, _, _, _, _, ship_x, _, _ in events] + [
        f"{first_x:.1f}",
        f"{first_x:.1f}",
    ]

    shots_svg = []
    for _, _, _, _, cx, cy, _, t_arrive, t_hit in events:
        shot_x = cx - 1.5
        t_end_shot = round(t_hit + 0.01, 3)
        shots_svg.append(
            f'<rect x="{shot_x:.1f}" y="{cy:.1f}" width="3" height="8" rx="1.5" fill="{LASER_COLOR}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{t_arrive}s" dur="{dt_shot}s" fill="remove" />'
            f'<animate attributeName="y" from="{ship_y - 3:.1f}" to="{cy:.1f}" '
            f'dur="{dt_shot}s" begin="{t_arrive}s" repeatCount="indefinite" />'
            f'<set attributeName="opacity" to="0" begin="{t_end_shot}s" fill="freeze" />'
            f'</rect>'
        )

    ship_svg = (
        f'<g transform="translate(0 {ship_y:.1f})">'
        f'<animateTransform attributeName="transform" additive="sum" type="translate" '
        f'values="{";".join(ship_val)}" keyTimes="{";".join(ship_kt)}" '
        f'dur="{total_dur}s" repeatCount="indefinite" />'
        f'<polygon points="10,0 18,10 13,10 13,12 7,12 7,10 2,10" fill="{SHIP_COLOR}" />'
        f'<rect x="9" y="3" width="2" height="4" fill="#e0f2fe" />'
        f'</g>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <rect width="{width}" height="{height}" rx="6" fill="{BG_COLOR}" />
  <g id="grid">
    {"".join(all_cells_svg)}
  </g>
  <g id="shots">
    {"".join(shots_svg)}
  </g>
  <g id="ship">
    {ship_svg}
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
