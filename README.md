
WindowsでFPS向けに常時表示できる中心点レティクルを表示するためのツールです。

## 使い方

1. Windows環境で `python Reticle_FPS.py` を実行します。
2. 画面中央に半透明のウィンドウが表示され、その中央に直径2px・色`#00E33A`のドットが描画されます。
3. 次のホットキーで操作できます。
   - `Ctrl + Alt + C` : レティクルの表示/非表示を切り替え
   - `Ctrl + Alt + Q` : アプリの終了

## カスタマイズ

`Reticle_FPS.py` はコマンドライン引数でレティクルを柔軟にカスタマイズできます。

### 既定の2px・#00E33Aにするには？

何もオプションを付けずに `python Reticle_FPS.py` を実行すると、直径2px・色 `“#00E33A”` のドットが表示されます。
明示的に指定したい場合は次のコマンドを使ってください。

```powershell
python Reticle_FPS.py --diameter 2 --color #00E33A
```

色やサイズを毎回指定するのが面倒な場合は、`Reticle_FPS.py` 冒頭の `DEFAULT_...` 定数を編集すれば既定値を変更できます。コマンドライン引数を渡した場合は、常にそちらが優先されます。

| オプション | 説明 |
| --------- | ---- |
| `--radius <px>` | ドットの半径（px）。`--diameter`（またはエイリアスの `--size`）を指定した場合はそちらが優先されます。既定値は1（直径2px）。 |
| `--diameter <px>` / `--size <px>` | ドットの直径（px）。奇数でも自動的に中央に配置されます。 |
| `--color <hex>` | ドットの色。`#RRGGBB` や `#RRGGBBAA` 形式を指定できます。既定値は `#00E33A`。 |
| `--outline-color <hex>` | 枠線の色。`--outline-width` と併用してください。 |
| `--outline-width <px>` | 枠線の太さ（px）。`0` で枠線なし。 |
| `--alpha <0-255>` | ウィンドウ全体の不透明度。省略時は色に含まれるアルファ値か255を使用します。 |
| `--hotkey-toggle <key>` | 表示切り替えホットキー（Tkのバインディング形式）。 |
| `--hotkey-quit <key>` | 終了用ホットキー。 |

例: `python Reticle_FPS.py --radius 6 --color #ff0000cc --outline-color #000000 --outline-width 2`

ドット以外の領域はクリックを透過するため、ゲームなどの操作を阻害しません。
