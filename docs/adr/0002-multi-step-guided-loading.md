# Carga guiada paso a paso para fixtures multi-step

Los fixtures con `type: multi-step` contienen varios steps que deben enviarse como turns separados de conversación. Decidimos usar carga guiada: al hacer clic, el step 1 se pre-carga en el textarea; tras enviarlo, el frontend detecta el step pendiente y pre-carga el step 2 automáticamente.

La alternativa de envío automático en cadena (el frontend envía todos los steps sin interacción del usuario) elimina la visibilidad del comportamiento del modelo entre pasos, que es el valor pedagógico central del lab. En un entorno de investigación, el investigador necesita observar la respuesta de Clara a cada step antes de decidir si continuar.
