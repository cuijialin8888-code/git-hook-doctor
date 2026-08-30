[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$script:ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script:Assets = Join-Path $script:ProjectRoot 'assets'

function New-RoundedPath {
    param(
        [System.Drawing.RectangleF]$Rectangle,
        [float]$Radius
    )
    $diameter = $Radius * 2
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $path.AddArc($Rectangle.X, $Rectangle.Y, $diameter, $diameter, 180, 90)
    $path.AddArc($Rectangle.Right - $diameter, $Rectangle.Y, $diameter, $diameter, 270, 90)
    $path.AddArc($Rectangle.Right - $diameter, $Rectangle.Bottom - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($Rectangle.X, $Rectangle.Bottom - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

function New-Canvas {
    param([int]$Width, [int]$Height)
    $bitmap = [System.Drawing.Bitmap]::new($Width, $Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $bitmap.SetResolution(144, 144)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    return @($bitmap, $graphics)
}

function Save-Canvas {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [System.Drawing.Graphics]$Graphics,
        [string]$Name
    )
    $path = [System.IO.Path]::GetFullPath((Join-Path $script:Assets $Name))
    if (-not $path.StartsWith($script:Assets, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Asset path escaped project assets directory: $path"
    }
    $Graphics.Dispose()
    $Bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $Bitmap.Dispose()
    Write-Output $path
}

function Get-Font {
    param([string]$Family, [float]$Size, [System.Drawing.FontStyle]$Style = [System.Drawing.FontStyle]::Regular)
    try {
        return [System.Drawing.Font]::new($Family, $Size, $Style, [System.Drawing.GraphicsUnit]::Pixel)
    }
    catch {
        return [System.Drawing.Font]::new('Segoe UI', $Size, $Style, [System.Drawing.GraphicsUnit]::Pixel)
    }
}

function Draw-LogoMark {
    param(
        [System.Drawing.Graphics]$Graphics,
        [float]$X,
        [float]$Y,
        [float]$Size
    )
    $scale = $Size / 256.0
    $rect = [System.Drawing.RectangleF]::new($X, $Y, $Size, $Size)
    $background = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
        $rect,
        [System.Drawing.ColorTranslator]::FromHtml('#101B33'),
        [System.Drawing.ColorTranslator]::FromHtml('#080D18'),
        45
    )
    $rounded = New-RoundedPath -Rectangle ([System.Drawing.RectangleF]::new($X + 12*$scale, $Y + 12*$scale, 232*$scale, 232*$scale)) -Radius (48*$scale)
    $Graphics.FillPath($background, $rounded)
    $border = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#263552'), 4*$scale)
    $Graphics.DrawPath($border, $rounded)

    $cyan = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#55DDF5'), 18*$scale)
    $cyan.StartCap = $cyan.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $hookPath = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $hookPath.StartFigure()
    $hookPath.AddLine($X + 74*$scale, $Y + 66*$scale, $X + 132*$scale, $Y + 66*$scale)
    $hookPath.AddArc($X + 132*$scale, $Y + 66*$scale, 112*$scale, 112*$scale, 270, 180)
    $hookPath.AddLine($X + 132*$scale, $Y + 178*$scale, $X + 118*$scale, $Y + 178*$scale)
    $Graphics.DrawPath($cyan, $hookPath)
    $Graphics.FillEllipse([System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#0B1220')), $X + 53*$scale, $Y + 49*$scale, 34*$scale, 34*$scale)
    $Graphics.DrawEllipse([System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#67E8F9'), 10*$scale), $X + 53*$scale, $Y + 49*$scale, 34*$scale, 34*$scale)

    $green = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#4ADE80'), 18*$scale)
    $green.StartCap = $green.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $green.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $Graphics.DrawLines($green, [System.Drawing.PointF[]]@(
        [System.Drawing.PointF]::new($X + 71*$scale, $Y + 145*$scale),
        [System.Drawing.PointF]::new($X + 95*$scale, $Y + 169*$scale),
        [System.Drawing.PointF]::new($X + 143*$scale, $Y + 111*$scale)
    ))

    foreach ($item in @($green, $cyan, $border, $hookPath, $rounded, $background)) { $item.Dispose() }
}

function Render-Logo {
    $canvas = New-Canvas -Width 512 -Height 512
    $bitmap = $canvas[0]
    $graphics = $canvas[1]
    $graphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#080D18'))
    Draw-LogoMark -Graphics $graphics -X 0 -Y 0 -Size 512
    Save-Canvas -Bitmap $bitmap -Graphics $graphics -Name 'logo.png'
}

function Render-Demo {
    $canvas = New-Canvas -Width 1200 -Height 640
    $bitmap = $canvas[0]
    $graphics = $canvas[1]
    $backgroundRect = [System.Drawing.RectangleF]::new(0, 0, 1200, 640)
    $background = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
        $backgroundRect,
        [System.Drawing.ColorTranslator]::FromHtml('#0C162B'),
        [System.Drawing.ColorTranslator]::FromHtml('#070B14'),
        45
    )
    $graphics.FillRectangle($background, $backgroundRect)
    $cardRect = [System.Drawing.RectangleF]::new(70, 54, 1060, 532)
    $card = New-RoundedPath -Rectangle $cardRect -Radius 20
    $graphics.FillPath([System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#0A0F1C')), $card)
    $graphics.DrawPath([System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#263552'), 2), $card)
    $graphics.DrawLine([System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#263552'), 2), 70, 110, 1130, 110)
    foreach ($dot in @(
        @{ X = 106; C = '#FB7185' },
        @{ X = 134; C = '#FBBF24' },
        @{ X = 162; C = '#4ADE80' }
    )) {
        $graphics.FillEllipse([System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml($dot.C)), $dot.X - 8, 74, 16, 16)
    }

    $mono = Get-Font -Family 'Cascadia Mono' -Size 22
    $monoBold = Get-Font -Family 'Cascadia Mono' -Size 22 -Style ([System.Drawing.FontStyle]::Bold)
    $titleFont = Get-Font -Family 'Cascadia Mono' -Size 18
    $white = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#E6EDF7'))
    $muted = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#93A4BF'))
    $cyan = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#67E8F9'))
    $green = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#4ADE80'))
    $yellow = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#FBBF24'))
    $red = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#FB7185'))
    $format = [System.Drawing.StringFormat]::new()
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $graphics.DrawString('git-hook-doctor', $titleFont, $muted, [System.Drawing.RectangleF]::new(420, 70, 360, 30), $format)
    $graphics.DrawString('$', $mono, $green, 104, 132)
    $graphics.DrawString('git-hook-doctor explain pre-commit', $mono, $white, 132, 132)
    $graphics.DrawString('Git Hook Doctor 0.1.0', $monoBold, $cyan, 104, 180)
    $graphics.DrawString('Git: 2.55.0  |  linked worktree', $mono, $muted, 104, 218)
    $graphics.DrawString('Hook directory: repo/.worktrees/feature/.githooks', $mono, $muted, 104, 254)
    $graphics.DrawString('Safety: read-only; no hooks executed', $mono, $muted, 104, 290)
    $graphics.DrawString('[BLOCKED] pre-commit', $monoBold, $red, 104, 344)
    $graphics.DrawString('ERROR GHD010', $mono, $yellow, 104, 382)
    $graphics.DrawString('Shebang uses CRLF line endings', $mono, $white, 294, 382)
    $graphics.DrawString('The carriage return becomes part of the interpreter name.', $mono, $muted, 132, 416)
    $graphics.DrawString('ERROR GHD012', $mono, $yellow, 104, 464)
    $graphics.DrawString('Hook interpreter is unavailable', $mono, $white, 294, 464)
    $graphics.DrawString("'python3' cannot be resolved where Git will start the hook.", $mono, $muted, 132, 498)
    $graphics.DrawString('Fix:', $mono, $cyan, 104, 537)
    $graphics.DrawString('store hooks as LF and install the interpreter.', $mono, $white, 165, 537)

    foreach ($item in @($format, $red, $yellow, $green, $cyan, $muted, $white, $titleFont, $monoBold, $mono, $card, $background)) { $item.Dispose() }
    Save-Canvas -Bitmap $bitmap -Graphics $graphics -Name 'demo.png'
}

function Render-SocialPreview {
    $canvas = New-Canvas -Width 1280 -Height 640
    $bitmap = $canvas[0]
    $graphics = $canvas[1]
    $backgroundRect = [System.Drawing.RectangleF]::new(0, 0, 1280, 640)
    $background = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
        $backgroundRect,
        [System.Drawing.ColorTranslator]::FromHtml('#101B33'),
        [System.Drawing.ColorTranslator]::FromHtml('#05080F'),
        38
    )
    $graphics.FillRectangle($background, $backgroundRect)
    Draw-LogoMark -Graphics $graphics -X 98 -Y 168 -Size 244

    $heading = Get-Font -Family 'Segoe UI' -Size 72 -Style ([System.Drawing.FontStyle]::Bold)
    $subtitle = Get-Font -Family 'Segoe UI' -Size 34
    $mono = Get-Font -Family 'Cascadia Mono' -Size 23
    $caps = Get-Font -Family 'Segoe UI' -Size 23 -Style ([System.Drawing.FontStyle]::Bold)
    $white = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#F3F7FF'))
    $muted = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#A9B7CE'))
    $cyan = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#67E8F9'))
    $green = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#4ADE80'))
    $graphics.DrawString('Git Hook Doctor', $heading, $white, 398, 184)
    $graphics.DrawString("Explain why a Git hook will - or won't - run.", $subtitle, $muted, 402, 292)
    $terminal = New-RoundedPath -Rectangle ([System.Drawing.RectangleF]::new(402, 382, 730, 86)) -Radius 14
    $graphics.FillPath([System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#080D18')), $terminal)
    $graphics.DrawPath([System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#263552'), 2), $terminal)
    $graphics.DrawString('$', $mono, $green, 433, 409)
    $graphics.DrawString('git-hook-doctor explain pre-commit', $mono, $white, 465, 409)
    $labels = @(
        @{ X = 402; Text = 'READ-ONLY' },
        @{ X = 575; Text = 'OFFLINE' },
        @{ X = 700; Text = 'CROSS-PLATFORM' },
        @{ X = 957; Text = 'NO HOOKS EXECUTED' }
    )
    foreach ($label in $labels) { $graphics.DrawString($label.Text, $caps, $cyan, $label.X, 508) }

    foreach ($item in @($terminal, $green, $cyan, $muted, $white, $caps, $mono, $subtitle, $heading, $background)) { $item.Dispose() }
    Save-Canvas -Bitmap $bitmap -Graphics $graphics -Name 'social-preview.png'
}

if (-not (Test-Path -LiteralPath $script:Assets -PathType Container)) {
    throw "Assets directory not found: $script:Assets"
}

Render-Logo
Render-Demo
Render-SocialPreview
