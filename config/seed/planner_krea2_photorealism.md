# KREA 2 - FOTOREALISMO

Esta regla aplica SOLO al string `prompt` de cada escena.
El contrato de salida no cambia: responde únicamente el JSON del planificador (`illustrate`, `reason`, `scenes`).
No preguntes al usuario. No uses formato markdown de respuesta (`## Prompt`, variaciones, modelo recomendado).
No generes negative prompts ni JSON de automatización. No inventes texto de UI.
Cada `prompt` va en inglés, un párrafo de prosa. Solo lo que el relato muestra.
Nombra materiales y de dónde cae la luz (Krea 2).

El modelo de imagen es Krea 2 Large. Escribe como fotografía real, no como ilustración.

Si otra regla fija el encuadre (por ejemplo `POV.`), no lo sustituyas: aplica fotorrealismo a luz, materiales, piel, lente y grano.

## Describe las imágenes así

Orden del párrafo (omite lo que el relato no muestre):

1. Tipo de imagen: `photograph`, `candid photo`, `portrait`, `close-up photograph`. Nunca `digital art`, `painting`, `illustration`, `3D render`, `CGI`, `anime`, `cartoon`.
2. Sujeto: cuántas personas, edad aparente, expresión, peinado. Ropa con color, tejido y desgaste. Pose concreta y quieta: cómo está el cuerpo en este instante, no la acción en curso.
3. Entorno: interior o exterior, lugar, hora del día, clima. Superficies tocables (madera, cuero, asfalto mojado, vapor, tela).
4. Luz: dirección, color y calidad. Sombras suaves o duras. Paleta dominante.
5. Cámara: encuadre, ángulo, lente 35–85 mm, profundidad de campo, grano de película si encaja.

Plantilla:

```text
A [photograph / candid photo / portrait] of [subject with clothes and still pose], in [place] at [time of day]. [Light: direction, color, quality]. [Lens and depth of field]. [Materials, color, atmosphere].
```

Vocabulario: `natural light`, `golden hour`, `overcast`, `soft side lighting`, `warm lamp light`, `shallow depth of field`, `50mm`, `85mm`, `film grain`, `35mm film`, `handheld`, `realistic skin texture`, `fabric weave`.

Retratos: piel con poros y variación de tono, no porcelana. Manos naturales. Expresión que el relato muestre, no una sonrisa genérica.

## Qué no hacer

No uses calificadores vacíos: `beautiful`, `cinematic`, `8k`, `masterpiece`, `high quality`, `ultra realistic`.
No inventes vestuario, personajes ni sitios.
No describas varias acciones seguidas; congela un fotograma.
No pongas en el prompt parámetros de API ni sintaxis de otros modelos.
No niegues defectos. Di el resultado deseado: `sharp focus on the face`, `natural hands`, `realistic skin`.

## Ejemplos

```text
A candid photograph of two young women sitting at a kitchen table in morning sunlight, one in a floral dress, the other in blue jeans and a white cotton t-shirt, both mid-laugh. Warm daylight from a window on the left, soft shadows on wood. 50mm, shallow depth of field, photorealistic skin and fabric texture.
```

```text
A close-up photograph of a middle-aged woman with curly hair, a slight smile, soft side light raking her cheek and catching stray hairs. Blurred room behind her. 85mm, shallow depth of field, realistic skin texture, analog grain.
```

```text
A candid street photograph of a man and a woman walking under umbrellas on wet city asphalt at night, rain jackets and jeans, neon storefronts reflecting in puddles. Overcast sodium and magenta light. 50mm, handheld, film grain, photorealistic.
```
