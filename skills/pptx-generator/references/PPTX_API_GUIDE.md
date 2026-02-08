# python-pptx API Guide

Reference documentation for python-pptx:

- https://python-pptx.readthedocs.io/en/latest/

Key modules frequently used in this skill:

- `pptx.Presentation`
- `pptx.util.Inches`, `pptx.util.Pt`
- `pptx.dml.color.RGBColor`
- `pptx.enum.text.PP_ALIGN`
- `pptx.enum.shapes.MSO_SHAPE`
# python-pptx API Reference Guide

Quick reference for the python-pptx library used in this skill.

## Installation

```bash
pip install python-pptx
```

## Core Concepts

### Presentation Object

```python
from pptx import Presentation

# Create new presentation
prs = Presentation()

# Open existing presentation
prs = Presentation('existing.pptx')

# Set dimensions (16:9 widescreen)
from pptx.util import Inches
prs.slide_width = Inches(10)
prs.slide_height = Inches(5.625)

# Save
prs.save('output.pptx')
```

### Slide Layouts

```python
# Common layout indices (may vary by template)
# 0 - Title slide
# 1 - Title and content
# 2 - Section header
# 3 - Two content
# 4 - Comparison
# 5 - Title only
# 6 - Blank
# 7 - Content with caption
# 8 - Picture with caption

slide_layout = prs.slide_layouts[6]  # Blank
slide = prs.slides.add_slide(slide_layout)
```

### Shapes

```python
# Add textbox
from pptx.util import Inches, Pt

textbox = slide.shapes.add_textbox(
    left=Inches(1),      # X position
    top=Inches(1),       # Y position
    width=Inches(8),     # Width
    height=Inches(1)     # Height
)

# Access text frame
tf = textbox.text_frame
tf.text = "Hello World"
tf.word_wrap = True

# Add paragraphs
p = tf.add_paragraph()
p.text = "Second paragraph"
```

### Text Formatting

```python
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

paragraph = text_frame.paragraphs[0]

# Font properties
paragraph.font.name = "Arial"
paragraph.font.size = Pt(24)
paragraph.font.bold = True
paragraph.font.italic = True
paragraph.font.color.rgb = RGBColor(255, 0, 0)  # Red

# Alignment
paragraph.alignment = PP_ALIGN.CENTER
paragraph.alignment = PP_ALIGN.LEFT
paragraph.alignment = PP_ALIGN.RIGHT

# Spacing
paragraph.space_before = Pt(12)
paragraph.space_after = Pt(12)
paragraph.level = 0  # Indent level (0-8)
```

### Colors

```python
from pptx.dml.color import RGBColor

# Create RGB color
red = RGBColor(255, 0, 0)
custom = RGBColor(15, 23, 42)  # Slate-900

# Apply to text
paragraph.font.color.rgb = RGBColor(0, 0, 0)

# Apply to shape fill
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(255, 255, 255)
```

### Background

```python
# Slide background
background = slide.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = RGBColor(15, 23, 42)
```

### Images

```python
# Add picture
picture = slide.shapes.add_picture(
    image_file='image.png',
    left=Inches(1),
    top=Inches(1),
    width=Inches(4),      # Optional: maintains aspect if height omitted
    height=Inches(3)      # Optional: maintains aspect if width omitted
)
```

### Tables

```python
# Add table
rows, cols = 3, 4
table = slide.shapes.add_table(
    rows=rows,
    cols=cols,
    left=Inches(1),
    top=Inches(2),
    width=Inches(8),
    height=Inches(2)
).table

# Access cells
cell = table.cell(0, 0)  # row, col
cell.text = "Header"

# Merge cells
cell.merge(table.cell(0, 1))
```

### Charts (requires additional setup)

```python
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

chart_data = CategoryChartData()
chart_data.categories = ['Q1', 'Q2', 'Q3', 'Q4']
chart_data.add_series('Sales', (100, 200, 150, 300))

chart = slide.shapes.add_chart(
    XL_CHART_TYPE.COLUMN_CLUSTERED,
    Inches(1), Inches(1),
    Inches(8), Inches(4),
    chart_data
).chart
```

## Units

```python
from pptx.util import Inches, Pt, Cm, Emu

# Inches - most common for positioning
Inches(1)  # 1 inch

# Points - for font sizes
Pt(24)  # 24 point font

# Centimeters
Cm(2.5)  # 2.5 cm

# EMUs (English Metric Units) - internal unit
Emu(914400)  # = 1 inch
```

## Enumerations

```python
# Text alignment
from pptx.enum.text import PP_ALIGN
PP_ALIGN.LEFT
PP_ALIGN.CENTER
PP_ALIGN.RIGHT
PP_ALIGN.JUSTIFY

# Vertical alignment
from pptx.enum.text import MSO_ANCHOR
MSO_ANCHOR.TOP
MSO_ANCHOR.MIDDLE
MSO_ANCHOR.BOTTOM

# Shape types
from pptx.enum.shapes import MSO_SHAPE
MSO_SHAPE.RECTANGLE
MSO_SHAPE.ROUNDED_RECTANGLE
MSO_SHAPE.OVAL
```

## Error Handling

```python
from pptx.exc import PackageNotFoundError

try:
    prs = Presentation('missing.pptx')
except PackageNotFoundError:
    print("File not found")
```

## Best Practices

1. **Always use Inches/Pt for measurements** - More readable than raw EMU values
2. **Use blank layouts for custom slides** - Gives full control over positioning
3. **Set word_wrap on text frames** - Prevents text overflow
4. **Check image existence before adding** - Prevents runtime errors
5. **Use RGBColor for consistent colors** - Easier than theme colors

## Resources

- [python-pptx Documentation](https://python-pptx.readthedocs.io/)
- [GitHub Repository](https://github.com/scanny/python-pptx)
- [API Reference](https://python-pptx.readthedocs.io/en/latest/api/presentation.html)
