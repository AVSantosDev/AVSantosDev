
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

    # Seleciona alvos (blocos com contribuição > 0, limitados para manter o loop fluido)
    targets = []
    for c in range(cols):
        for r in range(rows):
            if grid[r][c] > 0:
                targets.append((r, c, grid[r][c]))
    targets = targets[:42]

    duration = max(8.0, len(targets) * 0.28 + 2.0)

    blocks_svg = []
    shots_svg = []
    ship_x_keyframes = []
    ship_time_keyframes = []

    # Posição inicial da nave
    start_x = pad_x
    ship_y = pad_y + grid_h + 12

    ship_time_keyframes.append("0")
    ship_x_keyframes.append(f"{start_x}")

    for idx, (r, c, level) in enumerate(targets):
        bx = pad_x + c * step
        by = pad_y + r * step
        color = LEVEL_COLORS.get(level, "#26a641")

        # Momento em que o tiro atinge o bloco (em segundos)
        t_hit = round(0.6 + idx * 0.25, 2)
        t_shot_start = round(max(0.0, t_hit - 0.16), 2)
        t_respawn = round(min(duration - 0.2, t_hit + 2.2), 2)

        # Nave alinha na coluna do alvo logo antes do disparo
        ship_center_x = bx + cell / 2 - 10
        t_align = round(max(0.0, t_shot_start - 0.08), 2)
        ship_time_keyframes.append(f"{t_align / duration:.4f}")
        ship_x_keyframes.append(f"{ship_center_x:.1f}")

        # Bloco encolhe/some ao ser atingido e reaparece perto do fim do loop
        if t_respawn > t_hit:
            key_times = f"0;{t_hit / duration:.4f};{(t_hit + 0.08) / duration:.4f};{t_respawn / duration:.4f};1"
            scale_vals = "1;1;0;0;1"
            op_vals = "1;1;0;0;1"
        else:
            key_times = f"0;{t_hit / duration:.4f};{(t_hit + 0.08) / duration:.4f};1"
            scale_vals = "1;1;0;0"
            op_vals = "1;1;0;0"

        cx = bx + cell / 2
        cy = by + cell / 2

        blocks_svg.append(
            f'<g transform="translate({cx:.1f} {cy:.1f})">'
            f'<rect x="{-cell/2:.1f}" y="{-cell/2:.1f}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
            f'<animate attributeName="opacity" values="{op_vals}" keyTimes="{key_times}" dur="{duration:.2f}s" repeatCount="indefinite" />'
            f'</rect>'
            f'<animateTransform attributeName="transform" additive="sum" type="scale" '
            f'values="{scale_vals}" keyTimes="{key_times}" dur="{duration:.2f}s" repeatCount="indefinite" />'
            f'</g>'
        )

        # Projétil (laser) subindo da nave até o bloco
        shot_x = bx + cell / 2 - 1.5
        shot_begin = f"{t_shot_start}s"
        shots_svg.append(
            f'<rect x="{shot_x:.1f}" y="{by:.1f}" width="3" height="8" rx="1.5" fill="#38bdf8" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.1;0.85;1" dur="0.18s" begin="{shot_begin}" repeatCount="indefinite" />'
            f'<animate attributeName="y" from="{ship_y:.1f}" to="{by:.1f}" dur="0.16s" begin="{shot_begin}" repeatCount="indefinite" />'
            f'</rect>'
        )

    ship_time_keyframes.append("1")
    ship_x_keyframes.append(f"{start_x}")

    # Renderiza células vazias (nível 0) como fundo fixo
    bg_cells = []
    for c in range(cols):
        for r in range(rows):
            if grid[r][c] == 0:
                bx = pad_x + c * step
                by = pad_y + r * step
                bg_cells.append(
                    f'<rect x="{bx}" y="{by}" width="{cell}" height="{cell}" rx="2" fill="{LEVEL_COLORS[0]}" />'
                )

    key_times_ship = ";".join(ship_time_keyframes)
    values_ship = ";".join(ship_x_keyframes)

    # Nave retro (20x12)
    ship_group = (
        f'<g transform="translate(0 {ship_y:.1f})">'
        f'<animateTransform attributeName="transform" additive="sum" type="translate" '
        f'values="{values_ship}" keyTimes="{key_times_ship}" dur="{duration:.2f}s" repeatCount="indefinite" />'
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
