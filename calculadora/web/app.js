/* Calculadora de viajes D&T — comportamiento de la pantalla.
   Los cálculos y formatos vienen de Python (window.pywebview.api); aquí solo se
   arma la interfaz, se leen los campos y se muestran los resultados. */
"use strict";

(() => {
  const CLAVES = ["adultos", "adultos_ninos", "adultos_ninos_infantes"];
  const TIPO_DE_CLAVE = { adultos_ninos: "NIÑOS", adultos_ninos_infantes: "INFANTES" };
  const CLASE_COLUMNA = { adultos: "col-adultos", adultos_ninos: "col-ninos", adultos_ninos_infantes: "col-infantes" };
  const NOMBRE_SINGULAR = { ADULTOS: "Adulto", "NIÑOS": "Niño", INFANTES: "Infante" };
  const NOTA_NORMAL = "Monto total de cada grupo · Diseñador: precio por persona";
  const RETARDO_CALCULO_MS = 120;
  const RETARDO_AYUDA_MS = 450;
  const RETARDO_NOVEDADES_MS = 500;
  const RETARDO_ACTUALIZACION_MS = 2500;
  const SONDEO_DESCARGA_MS = 150;
  const MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
  ];
  const DIAS = ["lu", "ma", "mi", "ju", "vi", "sá", "do"];

  const $ = (selector, raiz = document) => raiz.querySelector(selector);
  const $$ = (selector, raiz = document) => Array.from(raiz.querySelectorAll(selector));

  let api = null;
  let config = null;
  let iniciado = false;
  let filas = [];
  let siguienteId = 1;
  let secuencia = 0;
  let temporizador = null;
  let primeraVez = true;
  let flotante = null;
  let historialTitulo = "";
  let negociacionActual = null; // la cotización guardada o reabierta: {id, enlace, negociacion, referencia}

  // ------------------------------------------------------------ utilidades
  function icono(id, clase = "icono") {
    return `<svg class="${clase}"><use href="#${id}"/></svg>`;
  }

  function crear(html) {
    const plantilla = document.createElement("template");
    plantilla.innerHTML = html.trim();
    return plantilla.content.firstElementChild;
  }

  function texto(elemento, valor) {
    elemento.textContent = valor;
    return elemento;
  }

  /** Cambia el texto y, si cambió, da un destello corto para notar la actualización. */
  function poner(elemento, valor) {
    if (!elemento || elemento.textContent === valor) return;
    elemento.textContent = valor;
    if (primeraVez) return;
    elemento.classList.remove("cambio");
    void elemento.offsetWidth;
    elemento.classList.add("cambio");
  }

  function reportar(detalle) {
    try {
      if (api) api.registrar_error_pagina(String(detalle));
    } catch (_) {
      /* sin conexión con Python: no hay dónde registrarlo */
    }
  }

  window.addEventListener("error", (evento) => {
    reportar(evento.error && evento.error.stack ? evento.error.stack : evento.message);
  });
  window.addEventListener("unhandledrejection", (evento) => {
    const razon = evento.reason;
    reportar(razon && razon.stack ? razon.stack : razon);
  });

  // ---------------------------------------------------------------- inicio
  async function iniciar() {
    if (iniciado || !(window.pywebview && window.pywebview.api && window.pywebview.api.inicio)) return;
    iniciado = true;
    api = window.pywebview.api;
    config = await api.inicio();

    texto($("#titulo"), config.titulo);
    texto($("#version"), config.version);
    construirPersonas();
    construirPorPersona();
    config.fijos.forEach((base) => agregarFila(base, { enfocar: false, animar: false, calcular: false }));
    conectarEventos();
    $("#repartir").checked = Boolean(config.repartir_por_defecto);
    aplicarReparto(false);
    actualizarColumnas();
    actualizarReloj();
    if (config.historial) {
      historialTitulo = config.historial.titulo;
      ponerInsignia(config.historial.cantidad);
    }

    await calcular(false);
    try {
      await document.fonts.ready;
    } catch (_) {
      /* si la fuente no carga se usa la del sistema */
    }
    $("#app").classList.remove("cargando");
    primeraVez = false;
    const adultos = $('#personas input[data-tipo="ADULTOS"]');
    adultos.focus();
    adultos.select();
    api.listo();

    if (config.novedades) setTimeout(() => mostrarNovedades(config.novedades), RETARDO_NOVEDADES_MS);
    if (config.historial && config.historial.aviso) setTimeout(() => avisar(config.historial.aviso, "error", 6000), 900);
    setTimeout(revisarActualizacion, RETARDO_ACTUALIZACION_MS);
  }

  window.addEventListener("pywebviewready", iniciar);
  if (document.readyState !== "loading") setTimeout(iniciar, 0);
  else document.addEventListener("DOMContentLoaded", iniciar);

  // ----------------------------------------------------------------- reloj
  function actualizarReloj() {
    const ahora = new Date();
    const dos = (n) => String(n).padStart(2, "0");
    const horas12 = ahora.getHours() % 12 || 12;
    const sufijo = ahora.getHours() < 12 ? "AM" : "PM";
    texto($("#fecha"), `Fecha: ${dos(ahora.getDate())}/${dos(ahora.getMonth() + 1)}/${ahora.getFullYear()}`);
    texto($("#hora"), `Hora: ${dos(horas12)}:${dos(ahora.getMinutes())} ${sufijo}`);
    const hastaElMinuto = 60000 - (ahora.getSeconds() * 1000 + ahora.getMilliseconds());
    setTimeout(actualizarReloj, hastaElMinuto + 50);
  }

  // -------------------------------------------------------------- personas
  function construirPersonas() {
    const contenedor = $("#personas");
    config.tipos.forEach((tipo) => {
      const inicial = tipo.clave === "ADULTOS" ? "1" : "0";
      const bloque = crear(`
        <div class="persona">
          <div><div class="nombre"></div><div class="edad"></div></div>
          <div class="contador">
            <button type="button" tabindex="-1" data-paso="-1" aria-label="Quitar uno">${icono("i-menos")}</button>
            <input class="cantidad-persona" inputmode="numeric" maxlength="2" autocomplete="off" value="${inicial}" data-tipo="${tipo.clave}" />
            <button type="button" tabindex="-1" data-paso="1" aria-label="Agregar uno">${icono("i-mas")}</button>
          </div>
        </div>`);
      texto($(".nombre", bloque), tipo.nombre);
      texto($(".edad", bloque), tipo.edad);
      const entrada = $("input", bloque);
      entrada.setAttribute("aria-label", `${tipo.nombre}, ${tipo.edad}`);
      entrada.addEventListener("input", () => {
        const limpio = entrada.value.replace(/\D/g, "").slice(0, 2);
        if (limpio !== entrada.value) entrada.value = limpio;
        alCambiarPersonas();
      });
      entrada.addEventListener("focus", () => entrada.select());
      entrada.addEventListener("blur", () => {
        if (entrada.value === "") {
          entrada.value = "0";
          alCambiarPersonas();
        }
      });
      entrada.addEventListener("keydown", (evento) => {
        if (evento.key === "ArrowUp" || evento.key === "ArrowDown") {
          evento.preventDefault();
          cambiarCantidad(entrada, evento.key === "ArrowUp" ? 1 : -1);
        } else if (evento.key === "Enter" && !evento.ctrlKey) {
          evento.preventDefault();
          siguienteCampo(entrada);
        }
      });
      $$("button", bloque).forEach((boton) =>
        boton.addEventListener("click", () => {
          cambiarCantidad(entrada, Number(boton.dataset.paso));
          entrada.focus();
        })
      );
      contenedor.append(bloque);
    });
  }

  function cambiarCantidad(entrada, paso) {
    const valor = Math.min(99, Math.max(0, (parseInt(entrada.value, 10) || 0) + paso));
    entrada.value = String(valor);
    entrada.select();
    alCambiarPersonas();
  }

  function cantidad(tipo) {
    const entrada = $(`#personas input[data-tipo="${tipo}"]`);
    return entrada ? parseInt(entrada.value, 10) || 0 : 0;
  }

  function activo(tipo) {
    return tipo === "ADULTOS" || cantidad(tipo) > 0;
  }

  function alCambiarPersonas() {
    actualizarColumnas();
    programarCalculo();
  }

  // ------------------------------------------------------------- servicios
  function esMiscelaneos(fila) {
    return fila.base === config.miscelaneos;
  }

  function nombreTipo(tipo) {
    const encontrado = config.tipos.find((t) => t.clave === tipo);
    return encontrado ? encontrado.nombre : tipo;
  }

  function descripcionGrupo(clave) {
    if (clave === "adultos") return "Monto de los adultos";
    if (clave === "adultos_ninos") return "Monto de adultos + niños";
    return activo("NIÑOS") ? "Monto de adultos + niños + infantes" : "Monto de adultos + infantes";
  }

  function agregarFila(base, { enfocar = true, animar = true, calcular: recalcular = true } = {}) {
    const info = config.servicios[base];
    const fila = { id: siguienteId++, base, fijo: info.fijo, entradas: {}, marcas: {}, subtipo: null };
    const elemento = crear('<div class="fila-servicio"></div>');
    if (!animar) elemento.style.animation = "none";

    const celdaNombre = document.createElement("div");
    if (esMiscelaneos(fila)) {
      const selector = crear('<select class="selector" aria-label="Tipo de misceláneo"></select>');
      config.subtipos_miscelaneos.forEach((subtipo) => selector.append(new Option(subtipo, subtipo)));
      selector.addEventListener("change", () => programarCalculo());
      fila.subtipo = selector;
      celdaNombre.append(selector);
    } else {
      celdaNombre.append(texto(crear('<div class="nombre-servicio"></div>'), info.nombre));
      if (info.por_persona) celdaNombre.append(texto(crear('<div class="detalle"></div>'), "precio por persona"));
    }
    elemento.append(celdaNombre);

    CLAVES.forEach((clave) => {
      const celda = crear(`<div class="celda-monto ${CLASE_COLUMNA[clave]}"></div>`);
      const tipo = TIPO_DE_CLAVE[clave];
      if (esMiscelaneos(fila) && tipo) {
        const marca = crear(`
          <label class="casilla pequena">
            <input type="checkbox" class="oculto-accesible" />
            <span class="caja"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span>
          </label>`);
        marca.dataset.ayuda = `Incluir ${nombreTipo(tipo).toLowerCase()} en este servicio`;
        const casilla = $("input", marca);
        casilla.setAttribute("aria-label", marca.dataset.ayuda);
        casilla.addEventListener("change", () => {
          actualizarFila(fila);
          programarCalculo();
          if (casilla.checked) fila.entradas[clave].focus();
        });
        fila.marcas[tipo] = casilla;
        celda.append(marca);
      }
      const entrada = crear('<input class="campo monto" value="$ 0.00" autocomplete="off" />');
      entrada.dataset.clave = clave;
      conectarMonto(entrada, () => resaltar(fila, clave), () => quitarResalte(fila));
      fila.entradas[clave] = entrada;
      celda.append(entrada);
      elemento.append(celda);
    });

    // Repartir monto: un solo total y las etiquetas con lo que le toca a cada tipo
    const celdaTotal = crear('<div class="celda-monto col-total"></div>');
    const total = crear('<input class="campo monto" value="$ 0.00" autocomplete="off" />');
    total.dataset.clave = "total";
    total.dataset.ayuda = info.por_persona
      ? "Precio por persona: se multiplica por todas las personas (niños e infantes también)"
      : "Total del grupo completo";
    conectarMonto(total, () => resaltar(fila, "total"), () => quitarResalte(fila));
    fila.entradas.total = total;
    celdaTotal.append(total);
    elemento.append(celdaTotal);
    const celdaReparto = crear('<div class="col-reparto"><div class="reparto"></div></div>');
    fila.reparto = $(".reparto", celdaReparto);
    fila.marcasReparto = {};
    if (esMiscelaneos(fila)) {
      const marcas = crear('<div class="marcas-reparto"></div>');
      celdaReparto.insertBefore(marcas, fila.reparto);
      ["NIÑOS", "INFANTES"].forEach((tipo) => {
        const marca = crear(`
          <label class="casilla pequena">
            <input type="checkbox" class="oculto-accesible" />
            <span class="caja"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span>
            ${nombreTipo(tipo)}
          </label>`);
        marca.dataset.ayuda = `Incluir ${nombreTipo(tipo).toLowerCase()} en este servicio`;
        const casilla = $("input", marca);
        casilla.addEventListener("change", () => {
          fila.marcas[tipo].checked = casilla.checked;
          actualizarFila(fila);
          programarCalculo();
        });
        fila.marcasReparto[tipo] = casilla;
        marcas.append(marca);
      });
    }
    elemento.append(celdaReparto);

    const celdaQuitar = crear('<div class="celda-quitar"></div>');
    if (!fila.fijo) {
      const quitar = crear(`<button type="button" class="boton-icono quitar" data-ayuda="Quitar servicio" aria-label="Quitar servicio">${icono("i-cerrar")}</button>`);
      quitar.addEventListener("click", () => quitarFila(fila));
      celdaQuitar.append(quitar);
    }
    elemento.append(celdaQuitar);
    // Al salir de la fila se muestran los avisos que se habían guardado mientras se escribía.
    elemento.addEventListener("focusout", () =>
      setTimeout(() => {
        if (!elemento.contains(document.activeElement)) dibujarAvisos(ultimosAvisos);
      }, 0)
    );

    fila.elemento = elemento;
    filas.push(fila);
    $("#cuerpo-servicios").append(elemento);
    actualizarFila(fila);
    if (enfocar) camposEditables(fila)[0].focus();
    if (recalcular) programarCalculo();
    return fila;
  }

  function quitarFila(fila) {
    if (fila.fijo || !filas.includes(fila)) return;
    const teniaFoco = fila.elemento.contains(document.activeElement);
    filas = filas.filter((otra) => otra !== fila);
    ocultarAyuda();
    fila.elemento.classList.add("saliendo");
    const retirar = () => fila.elemento.remove();
    fila.elemento.addEventListener("animationend", retirar, { once: true });
    setTimeout(retirar, 400);
    if (teniaFoco) $("#agregar-servicio").focus();
    programarCalculo();
  }

  function actualizarFila(fila) {
    CLAVES.forEach((clave) => {
      const tipo = TIPO_DE_CLAVE[clave];
      const entrada = fila.entradas[clave];
      entrada.dataset.ayuda = descripcionGrupo(clave);
      if (tipo && esMiscelaneos(fila)) entrada.disabled = !(activo(tipo) && fila.marcas[tipo].checked);
    });
    Object.entries(fila.marcasReparto || {}).forEach(([tipo, casilla]) => {
      casilla.checked = fila.marcas[tipo].checked;
      casilla.closest("label").style.display = activo(tipo) ? "" : "none";
    });
  }

  function repartiendo() {
    return $("#repartir").checked;
  }

  /** Enciende o apaga "Repartir monto". El total y la columna del grupo completo
      (la última columna activa) son el mismo dato: al cambiar de modo se copia de uno
      al otro, para que nunca quede un monto viejo. */
  function pintarModoReparto() {
    const encendido = repartiendo();
    $("#tabla-servicios").classList.toggle("repartir", encendido);
    const pesos = config.pesos_reparto || {};
    texto(
      $("#nota-servicios"),
      encendido
        ? `Total del grupo (Diseñador: por persona) · Se reparte: adulto ${pesos.ADULTOS} · niño ${pesos["NIÑOS"]} · infante ${pesos.INFANTES}`
        : NOTA_NORMAL
    );
  }

  function aplicarReparto(recalcular = true) {
    const encendido = repartiendo();
    pintarModoReparto();
    const clave = activo("INFANTES") ? "adultos_ninos_infantes" : activo("NIÑOS") ? "adultos_ninos" : "adultos";
    filas.forEach((fila) => {
      const total = fila.entradas.total;
      const grupo = fila.entradas[clave];
      if (grupo.disabled) return; // Misceláneos sin ese tipo marcado
      const [origen, destino] = encendido ? [grupo, total] : [total, grupo];
      // Al apagar solo se actualiza una columna que ya se usaba: un servicio agregado con el
      // interruptor encendido no tiene las otras columnas y quedaría a medias.
      if (!encendido && textoEditable(grupo.value) === "") return;
      if (textoEditable(origen.value) !== "") {
        destino.value = origen.value;
        destino.classList.remove("invalido");
      }
    });
    ocultarAyuda();
    if (recalcular) calcular(false);
  }

  function actualizarColumnas() {
    const tabla = $("#tabla-servicios");
    const hayNinos = activo("NIÑOS");
    const hayInfantes = activo("INFANTES");
    tabla.classList.toggle("sin-ninos", !hayNinos);
    tabla.classList.toggle("sin-infantes", !hayInfantes);
    texto($("#enc-combinado"), hayNinos ? "Adultos + niños + infantes" : "Adultos + infantes");
    filas.forEach(actualizarFila);
    $$("#por-persona .bloque-tipo").forEach((bloque) => {
      const visible = activo(bloque.dataset.tipo);
      if (visible && bloque.classList.contains("oculto")) {
        bloque.classList.remove("oculto");
        bloque.classList.add("entrando");
        setTimeout(() => bloque.classList.remove("entrando"), 250);
      } else if (!visible) {
        bloque.classList.add("oculto");
      }
    });
  }

  function resaltar(fila, clave) {
    filas.forEach((otra) => otra.elemento.classList.toggle("enfocada", otra === fila));
    $$("#encabezado-servicios [data-clave]").forEach((celda) =>
      celda.classList.toggle("activa", celda.dataset.clave === clave)
    );
  }

  function quitarResalte(fila) {
    fila.elemento.classList.remove("enfocada");
    $$("#encabezado-servicios [data-clave]").forEach((celda) => celda.classList.remove("activa"));
  }

  // ----------------------------------------------------------- campos de monto
  /** Al entrar al campo se quita el formato ("$ 1,000.00" -> "1000") para escribir cómodo. */
  function textoEditable(valor) {
    const limpio = valor.replace(/[$,\s]/g, "");
    if (limpio === "" || Number(limpio) === 0) return "";
    return limpio.endsWith(".00") ? limpio.slice(0, -3) : limpio;
  }

  async function formatear(entrada, permitirVacio = false) {
    const valor = entrada.value;
    if (permitirVacio && !valor.trim()) return;
    const respuesta = await api.formatear_monto(valor);
    if (document.activeElement === entrada || entrada.value !== valor) return; // ya lo volvió a editar
    if (respuesta && respuesta.valido) {
      entrada.value = respuesta.texto;
      entrada.classList.remove("invalido");
    } else {
      entrada.classList.add("invalido");
    }
  }

  function conectarMonto(entrada, alEnfocar, alSalir, permitirVacio = false) {
    entrada.addEventListener("focus", () => {
      entrada.value = textoEditable(entrada.value);
      entrada.select();
      if (alEnfocar) alEnfocar();
    });
    entrada.addEventListener("blur", () => {
      formatear(entrada, permitirVacio);
      if (alSalir) alSalir();
    });
    entrada.addEventListener("input", () => {
      entrada.classList.remove("invalido");
      programarCalculo();
    });
    entrada.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" && !evento.ctrlKey) {
        evento.preventDefault();
        siguienteCampo(entrada);
      }
    });
  }

  function camposEditables(fila) {
    if (repartiendo()) return [fila.entradas.total];
    return CLAVES.filter((clave) => {
      const tipo = TIPO_DE_CLAVE[clave];
      if (!tipo) return true;
      return activo(tipo) && (!esMiscelaneos(fila) || fila.marcas[tipo].checked);
    }).map((clave) => fila.entradas[clave]);
  }

  function ordenCampos() {
    const campos = $$("#personas input");
    filas.forEach((fila) => campos.push(...camposEditables(fila)));
    return campos;
  }

  /** Enter pasa al siguiente campo; en el último, calcula. */
  function siguienteCampo(actual) {
    if (actual.id === "ajuste-nuevo") {
      formatear(actual, true).then(() => programarCalculo());
      actual.blur();
      return;
    }
    const campos = ordenCampos();
    const indice = campos.indexOf(actual);
    if (indice === -1) return;
    if (indice === campos.length - 1) {
      actual.blur();
      calcular(true);
      return;
    }
    campos[indice + 1].focus();
  }

  // ------------------------------------------------------- menú y calendario
  function abrirFlotante(elemento, ancla) {
    cerrarFlotante(true);
    document.body.append(elemento);
    const caja = ancla.getBoundingClientRect();
    const alto = elemento.offsetHeight;
    const ancho = elemento.offsetWidth;
    let arriba = caja.bottom + 6;
    if (arriba + alto > window.innerHeight - 8) {
      arriba = Math.max(8, caja.top - alto - 6);
      elemento.style.transformOrigin = "bottom left";
    }
    const izquierda = Math.min(caja.left, window.innerWidth - ancho - 8);
    elemento.style.top = `${arriba}px`;
    elemento.style.left = `${Math.max(8, izquierda)}px`;
    flotante = { elemento, ancla };
  }

  function cerrarFlotante(inmediato = false) {
    if (!flotante) return;
    const { elemento } = flotante;
    flotante = null;
    if (inmediato) {
      elemento.remove();
      return;
    }
    elemento.classList.add("cerrando");
    elemento.addEventListener("animationend", () => elemento.remove(), { once: true });
    setTimeout(() => elemento.remove(), 300);
  }

  function abrirMenuServicios() {
    const boton = $("#agregar-servicio");
    if (flotante && flotante.ancla === boton) {
      cerrarFlotante();
      return;
    }
    const usados = new Set(filas.map((fila) => fila.base));
    const opciones = config.opcionales.filter((base) => base === config.miscelaneos || !usados.has(base));
    const menu = crear('<div class="flotante menu" role="menu"></div>');
    opciones.forEach((base) => {
      const opcion = texto(crear('<button type="button" role="menuitem"></button>'), config.servicios[base].nombre);
      opcion.addEventListener("click", () => {
        cerrarFlotante();
        agregarFila(base);
      });
      menu.append(opcion);
    });
    menu.addEventListener("keydown", (evento) => {
      const botones = $$("button", menu);
      const indice = botones.indexOf(document.activeElement);
      if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
        evento.preventDefault();
        const paso = evento.key === "ArrowDown" ? 1 : -1;
        botones[(indice + paso + botones.length) % botones.length].focus();
      }
    });
    abrirFlotante(menu, boton);
    const primero = $("button", menu);
    if (primero) primero.focus();
  }

  function leerFecha(valor) {
    const partes = valor.split("/");
    if (partes.length !== 3 || partes[2].length !== 4) return null;
    const [dia, mes, anio] = partes.map((p) => parseInt(p, 10));
    const fecha = new Date(anio, mes - 1, dia);
    if (fecha.getFullYear() !== anio || fecha.getMonth() !== mes - 1 || fecha.getDate() !== dia) return null;
    return fecha;
  }

  function formatoFecha(fecha) {
    const dos = (n) => String(n).padStart(2, "0");
    return `${dos(fecha.getDate())}/${dos(fecha.getMonth() + 1)}/${fecha.getFullYear()}`;
  }

  /** Mismo criterio que fechas.con_diagonales en Python: '25122026' -> '25/12/2026'. */
  function conDiagonales(valor) {
    const digitos = valor.replace(/\D/g, "").slice(0, 8);
    return [digitos.slice(0, 2), digitos.slice(2, 4), digitos.slice(4)].filter(Boolean).join("/");
  }

  function abrirCalendario(entrada, boton) {
    if (flotante && flotante.ancla === boton) {
      cerrarFlotante();
      return;
    }
    const elegida = leerFecha(entrada.value);
    const hoy = new Date();
    let vista = new Date((elegida || hoy).getFullYear(), (elegida || hoy).getMonth(), 1);
    const calendario = crear('<div class="flotante calendario" role="dialog" aria-label="Calendario"></div>');

    function mismoDia(a, b) {
      return a && b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
    }

    function dibujar() {
      calendario.innerHTML = `
        <div class="cabeza">
          <button type="button" class="boton-icono" data-mover="-1" aria-label="Mes anterior">${icono("i-flecha-izq")}</button>
          <span class="mes">${MESES[vista.getMonth()]} ${vista.getFullYear()}</span>
          <button type="button" class="boton-icono" data-mover="1" aria-label="Mes siguiente">${icono("i-flecha")}</button>
        </div>
        <div class="dias"></div>`;
      const dias = $(".dias", calendario);
      DIAS.forEach((dia) => dias.append(texto(crear('<span class="dia-semana"></span>'), dia)));
      const desplazamiento = (vista.getDay() + 6) % 7; // la semana empieza el lunes
      for (let i = 0; i < desplazamiento; i += 1) dias.append(crear('<span class="dia fuera"></span>'));
      const ultimo = new Date(vista.getFullYear(), vista.getMonth() + 1, 0).getDate();
      for (let numero = 1; numero <= ultimo; numero += 1) {
        const fecha = new Date(vista.getFullYear(), vista.getMonth(), numero);
        const dia = texto(crear('<button type="button" class="dia"></button>'), String(numero));
        if (mismoDia(fecha, hoy)) dia.classList.add("hoy");
        if (mismoDia(fecha, elegida)) dia.classList.add("elegido");
        dia.addEventListener("click", () => {
          entrada.value = formatoFecha(fecha);
          cerrarFlotante();
          entrada.focus();
          programarCalculo();
        });
        dias.append(dia);
      }
      $$("[data-mover]", calendario).forEach((mover) =>
        mover.addEventListener("click", () => {
          vista = new Date(vista.getFullYear(), vista.getMonth() + Number(mover.dataset.mover), 1);
          dibujar();
        })
      );
    }

    dibujar();
    abrirFlotante(calendario, boton);
    const enfoque = $(".dia.elegido", calendario) || $(".dia.hoy", calendario) || $(".dia:not(.fuera)", calendario);
    if (enfoque) enfoque.focus();
  }

  // ----------------------------------------------------------------- panel
  function construirPorPersona() {
    const tabla = $("#por-persona");
    tabla.append(
      crear('<div class="enc"></div>'),
      crear('<div class="enc col-pvp">PVP</div>'),
      crear('<div class="enc col-desc"><span>Con descuento</span></div>')
    );
    config.tipos.forEach((tipo) => {
      const bloque = crear(`
        <div class="bloque-tipo" data-tipo="${tipo.clave}">
          <div class="nombre-tipo"></div>
          <div class="valor precio col-pvp"><span class="copiable" data-campo="pvp">$ 0.00</span></div>
          <div class="valor precio col-desc"><span class="copiable" data-campo="descuento">$ 0.00</span></div>
          <div class="cantidad" data-campo="cantidad">× 0</div>
          <div class="valor secundario col-pvp"><span class="copiable" data-campo="pvp_q">Q 0.00</span></div>
          <div class="valor secundario col-desc"><span class="copiable" data-campo="descuento_q">Q 0.00</span></div>
          <div></div>
          <div class="valor secundario col-pvp"><span class="copiable" data-campo="pvp_total">Total $ 0.00</span></div>
          <div class="valor secundario col-desc"><span class="copiable" data-campo="descuento_total">Total $ 0.00</span></div>
        </div>`);
      texto($(".nombre-tipo", bloque), tipo.nombre);
      tabla.append(bloque);
    });
  }

  function aplicarDescuento() {
    medirDescuento();
    $("#panel").classList.toggle("con-descuento", $("#con-descuento").checked);
  }

  /** Ancho que necesita la columna "Con descuento" para mostrar las cifras completas. */
  function medirDescuento() {
    const panel = $("#panel");
    const ancho = (selector) =>
      Math.ceil(Math.max(0, ...$$(selector, panel).map((elemento) => elemento.offsetWidth))) + 2;
    panel.style.setProperty("--ancho-descuento-abierto", `${ancho(".por-persona .col-desc > *")}px`);
    panel.style.setProperty("--ancho-descuento-total-abierto", `${ancho(".resumen-totales .col-desc > *")}px`);
  }

  // --------------------------------------------------------------- cálculo
  function leerEstado() {
    const personas = {};
    $$("#personas input").forEach((entrada) => {
      personas[entrada.dataset.tipo] = entrada.value;
    });
    return {
      personas,
      servicios: filas.map((fila) => {
        const montos = {};
        CLAVES.concat("total").forEach((clave) => {
          montos[clave] = fila.entradas[clave].value;
        });
        const incluye = {};
        Object.entries(fila.marcas).forEach(([tipo, casilla]) => {
          incluye[tipo] = casilla.checked;
        });
        return { base: fila.base, subtipo: fila.subtipo ? fila.subtipo.value : null, montos, incluye };
      }),
      redondear: $("#redondear").checked,
      repartir: repartiendo(),
      no_reembolsable: $("#no-reembolsable").checked,
      fecha_viaje: $("#fecha-viaje").value,
      fecha_cancelacion: $("#fecha-cancelacion").value,
      ajuste_nuevo: $("#ajuste-nuevo").value,
    };
  }

  function programarCalculo() {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => calcular(false), RETARDO_CALCULO_MS);
  }

  async function calcular(explicito) {
    clearTimeout(temporizador);
    temporizador = null;
    const mia = ++secuencia;
    const resultado = await api.calcular(leerEstado());
    if (mia !== secuencia || !resultado) return; // llegó otra respuesta más nueva

    if (resultado.monto_reserva !== undefined) poner($("#monto-reserva"), resultado.monto_reserva);
    if (resultado.pago) mostrarPago(resultado.pago);
    $$(".fila-servicio .campo.invalido").forEach((campo) => campo.classList.remove("invalido"));

    if (!resultado.ok) {
      const campo = resultado.campo || {};
      if (campo.tipo === "monto" && filas[campo.fila]) {
        const entrada = filas[campo.fila].entradas[campo.clave];
        entrada.classList.add("invalido");
        if (explicito) entrada.focus();
      } else if (campo.tipo === "personas" && explicito) {
        $('#personas input[data-tipo="ADULTOS"]').focus();
      }
      if (explicito && resultado.mensaje) avisar(resultado.mensaje, "error");
      return;
    }
    mostrarResultados(resultado);
  }

  function mostrarPago(pago) {
    $("#bloque-fechas").classList.toggle("cerrado", !pago.visible);
    const campos = { viaje: $("#fecha-viaje"), cancelacion: $("#fecha-cancelacion") };
    // Una fecha a medio escribir no es un error todavía: se marca al salir del campo.
    const escribiendo = Boolean(pago.incompleta) && document.activeElement === campos[pago.campo];
    Object.entries(campos).forEach(([clave, campo]) =>
      campo.classList.toggle("invalido", pago.visible && !escribiendo && pago.campo === clave)
    );
    const aviso = $("#aviso-pago");
    if (!pago.visible) return;
    if (escribiendo) {
      aviso.className = "aviso-pago neutro";
      poner(aviso, "Escribe la fecha completa: dd/mm/aaaa.");
      return;
    }
    aviso.className = `aviso-pago ${pago.tono}`;
    poner(aviso, pago.texto);
  }

  /** Clic en una cifra: se copia tal como se ve ("$ 1,161.00" o "Q 9,149.00"). */
  async function copiarCifra(elemento) {
    const cifra = elemento.textContent.replace(/^Total\s+/, "").trim();
    if (!cifra || cifra === "—") return;
    const respuesta = await api.copiar_texto(cifra);
    if (!respuesta || !respuesta.ok) {
      avisar((respuesta && respuesta.mensaje) || "No se pudo copiar.", "error", 2500);
      return;
    }
    elemento.classList.remove("copiado");
    void elemento.offsetWidth;
    elemento.classList.add("copiado");
    avisar(`Copiado: ${cifra}`, "exito", 1300);
  }

  function mostrarResultados(resultado) {
    Object.entries(resultado.por_persona).forEach(([tipo, valores]) => {
      const bloque = $(`#por-persona .bloque-tipo[data-tipo="${tipo}"]`);
      if (!bloque) return;
      Object.entries(valores).forEach(([campo, valor]) => poner($(`[data-campo="${campo}"]`, bloque), valor));
    });
    poner($("#total-pvp"), resultado.totales.pvp);
    poner($("#total-pvp-q"), resultado.totales.pvp_q);
    poner($("#total-descuento"), resultado.totales.descuento);
    poner($("#total-descuento-q"), resultado.totales.descuento_q);
    poner($("#ajuste-actual"), resultado.ajuste.actual);
    poner($("#ajuste-diferencia"), resultado.ajuste.diferencia);
    (resultado.reparto || []).forEach((valores, indice) => dibujarReparto(filas[indice], valores));
    dibujarAvisos(resultado.avisos || []);
    medirDescuento();
    dibujarDesglose(resultado.desglose);
  }

  /** Franja amarilla debajo del servicio con una cotización atípica. */
  let ultimosAvisos = [];

  function dibujarAvisos(avisos) {
    ultimosAvisos = avisos;
    // Mientras se escribe en un servicio no se le avisa nada: se espera a salir de la fila.
    const enEdicion = filas.find((fila) => fila.elemento.contains(document.activeElement));
    const nuevos = new Map(
      avisos.filter((aviso) => filas[aviso.fila] !== enEdicion).map((aviso) => [filas[aviso.fila], aviso])
    );
    filas.forEach((fila) => {
      const aviso = nuevos.get(fila);
      const actual = fila.elemento.nextElementSibling;
      const tiene = actual && actual.classList.contains("aviso-fila") ? actual : null;
      Object.values(fila.entradas).forEach((entrada) =>
        entrada.classList.toggle("alerta", Boolean(aviso) && entrada.dataset.clave === aviso.clave)
      );
      if (!aviso) {
        if (tiene) tiene.remove();
        return;
      }
      const franja = tiene || crear(`<div class="aviso-fila" role="status">${icono("i-alerta")}<span></span></div>`);
      texto($("span", franja), aviso.mensaje);
      if (!tiene) fila.elemento.after(franja);
    });
    $$("#cuerpo-servicios .aviso-fila").forEach((franja) => {
      const anterior = franja.previousElementSibling;
      if (!anterior || !filas.some((fila) => fila.elemento === anterior) || !nuevos.has(filas.find((f) => f.elemento === anterior))) {
        franja.remove();
      }
    });
  }

  function dibujarReparto(fila, valores) {
    if (!fila) return;
    const etiquetas = Object.entries(valores).map(([tipo, valor]) => `${NOMBRE_SINGULAR[tipo]}|${valor}`);
    if (fila.reparto.dataset.valores === etiquetas.join(";")) return;
    fila.reparto.dataset.valores = etiquetas.join(";");
    fila.reparto.innerHTML = "";
    etiquetas.forEach((etiqueta) => {
      const [nombre, valor] = etiqueta.split("|");
      const chip = crear('<span class="chip"><span></span> <b></b></span>');
      texto(chip.firstElementChild, nombre);
      texto(chip.lastElementChild, valor);
      fila.reparto.append(chip);
    });
  }

  function dibujarDesglose(desglose) {
    const contenedor = $("#contenido-desglose");
    contenedor.innerHTML = "";
    if (!desglose.grupos.length) {
      contenedor.append(texto(crear('<div class="desglose-vacio"></div>'), "Todavía no hay montos para mostrar."));
      return;
    }
    const tabla = crear("<table class=\"tabla-desglose\"><thead><tr></tr></thead><tbody></tbody></table>");
    desglose.encabezados.forEach((titulo) => $("thead tr", tabla).append(texto(document.createElement("th"), titulo)));
    const cuerpo = $("tbody", tabla);
    desglose.grupos.forEach((grupo, indice) => {
      if (indice) cuerpo.append(crear('<tr class="separador"><td colspan="5"></td></tr>'));
      const encabezado = crear('<tr class="grupo"><td colspan="5"></td></tr>');
      texto($("td", encabezado), grupo.nombre);
      cuerpo.append(encabezado);
      grupo.renglones.forEach((renglon) => {
        const fila = document.createElement("tr");
        fila.append(texto(document.createElement("td"), renglon.concepto));
        renglon.valores.forEach((valor, columna) => {
          const celda = texto(document.createElement("td"), valor);
          if (columna >= 2) celda.className = "pvp";
          fila.append(celda);
        });
        cuerpo.append(fila);
      });
    });
    cuerpo.append(crear('<tr class="separador"><td colspan="5"></td></tr>'));
    const total = crear('<tr class="total"><td>TOTAL</td></tr>');
    desglose.totales.forEach((valor) => total.append(texto(document.createElement("td"), valor)));
    cuerpo.append(total);
    contenedor.append(tabla);
  }

  function alternarDesglose() {
    const boton = $("#boton-desglose");
    const abrir = boton.getAttribute("aria-expanded") !== "true";
    boton.setAttribute("aria-expanded", String(abrir));
    texto($("span", boton), abrir ? "Ocultar desglose" : "Ver desglose");
    $("#bloque-desglose").classList.toggle("cerrado", !abrir);
  }

  function limpiar() {
    cerrarFlotante(true);
    negociacionActual = null;
    $$("#personas input").forEach((entrada) => {
      entrada.value = entrada.dataset.tipo === "ADULTOS" ? "1" : "0";
    });
    filas.filter((fila) => !fila.fijo).forEach(quitarFila);
    filas.forEach((fila) => {
      Object.values(fila.entradas).forEach((entrada) => {
        entrada.value = "$ 0.00";
        entrada.classList.remove("invalido");
      });
    });
    $("#redondear").checked = true;
    $("#repartir").checked = Boolean(config.repartir_por_defecto);
    aplicarReparto(false);
    $("#con-descuento").checked = false;
    aplicarDescuento();
    $("#no-reembolsable").checked = false;
    $("#fecha-viaje").value = "";
    $("#fecha-cancelacion").value = "";
    $("#ajuste-nuevo").value = "";
    $("#convertir-q").value = "";
    $("#convertir-q").classList.remove("invalido");
    window.__ponerOrigenConversion?.("GTQ");
    texto($("#convertir-usd"), "$ 0.00");
    actualizarColumnas();
    calcular(false);
    const adultos = $('#personas input[data-tipo="ADULTOS"]');
    adultos.focus();
    adultos.select();
  }

  // ---------------------------------------------------------------- captura
  async function capturar() {
    const boton = $("#boton-captura");
    if (boton.disabled) return;
    boton.disabled = true;
    cerrarFlotante(true);
    ocultarAyuda();
    try {
      const app = $("#app");
      const lienzo = await window.html2canvas(app, {
        backgroundColor: "#EEF2F6",
        scale: Math.max(1, window.devicePixelRatio || 1),
        logging: false,
        onclone: prepararCaptura,
      });
      const respuesta = await api.copiar_captura(lienzo.toDataURL("image/png"), {
        estado: estadoCompleto(),
        referencia: negociacionActual ? negociacionActual.referencia : "",
        negociacion: negociacionActual ? negociacionActual.negociacion : "",
      });
      if (respuesta && respuesta.ok) {
        if (respuesta.copiada && respuesta.archivo) avisar(`Captura copiada y guardada · ${respuesta.archivo}`, "exito", 3200);
        else if (respuesta.archivo) avisar(`Captura guardada (no se pudo copiar) · ${respuesta.archivo}`, "error", 4000);
        else avisar("Captura copiada (no se pudo guardar el archivo)", "error", 4000);
        boton.classList.add("hecho");
        boton.innerHTML = icono("i-check");
        setTimeout(() => {
          boton.classList.remove("hecho");
          boton.innerHTML = icono("i-camara");
        }, 1200);
      } else {
        avisar((respuesta && respuesta.mensaje) || "No se pudo copiar la captura.", "error", 3500);
      }
    } catch (error) {
      reportar(error && error.stack ? error.stack : error);
      avisar("No se pudo copiar la captura.", "error", 3500);
    } finally {
      boton.disabled = false;
    }
  }

  /** Ajusta el clon que dibuja html2canvas para que se vea igual que la pantalla. */
  function prepararCaptura(documento) {
    const ventana = documento.defaultView;
    documento.getElementById("app").classList.add("capturando");
    // El desglose sale en la captura aunque esté plegado en la pantalla
    documento.getElementById("bloque-desglose").classList.remove("cerrado");
    const botonDesglose = documento.getElementById("boton-desglose");
    if (botonDesglose) botonDesglose.remove();

    // html2canvas no resuelve <use>: se copia el dibujo del símbolo dentro de cada ícono
    // y se fijan los colores calculados, porque el SVG se dibuja aparte, sin la hoja de estilos.
    documento.querySelectorAll("#app svg use").forEach((uso) => {
      const svg = uso.closest("svg");
      const simbolo = documento.getElementById((uso.getAttribute("href") || "").slice(1));
      if (simbolo) {
        svg.setAttribute("viewBox", simbolo.getAttribute("viewBox"));
        Array.from(simbolo.childNodes).forEach((nodo) => {
          const copia = nodo.cloneNode(true);
          // html2canvas ya les copió estilos calculados fuera del ícono (relleno negro): se quitan
          if (copia.nodeType === 1) {
            copia.removeAttribute("style");
            copia.querySelectorAll("[style]").forEach((hijo) => hijo.removeAttribute("style"));
          }
          svg.append(copia);
        });
      }
      uso.remove();
    });
    documento.querySelectorAll("#app svg").forEach((svg) => {
      const estilo = ventana.getComputedStyle(svg);
      svg.setAttribute("width", parseFloat(estilo.width) || 16);
      svg.setAttribute("height", parseFloat(estilo.height) || 16);
      [
        ["stroke", estilo.stroke],
        ["fill", estilo.fill],
        ["stroke-width", estilo.strokeWidth],
        ["stroke-linecap", estilo.strokeLinecap],
        ["stroke-linejoin", estilo.strokeLinejoin],
        ["stroke-dasharray", estilo.strokeDasharray],
        ["stroke-dashoffset", estilo.strokeDashoffset],
      ].forEach(([atributo, valor]) => {
        if (valor) svg.setAttribute(atributo, valor);
      });
      // Como imagen se dibuja siempre; como SVG suelto html2canvas a veces lo omite.
      const copia = svg.cloneNode(true);
      copia.removeAttribute("style");
      copia.removeAttribute("class");
      copia.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const imagen = documento.createElement("img");
      imagen.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(copia.outerHTML)}`;
      imagen.width = parseFloat(estilo.width) || 16;
      imagen.height = parseFloat(estilo.height) || 16;
      imagen.style.cssText = `display:block;flex:none;width:${imagen.width}px;height:${imagen.height}px;position:relative;z-index:1`;
      svg.replaceWith(imagen);
    });

    // Los campos se cambian por cajas con el mismo aspecto: html2canvas no centra bien su texto.
    documento.querySelectorAll("#app input:not([type=checkbox]), #app select").forEach((campo) => {
      const caja = documento.createElement("div");
      const estilo = ventana.getComputedStyle(campo);
      caja.className = `${campo.className} campo-captura`;
      caja.style.width = estilo.width;
      caja.style.height = estilo.height;
      let valor = campo.tagName === "SELECT" ? (campo.options[campo.selectedIndex] || {}).text || "" : campo.value;
      if (!valor && campo.placeholder) {
        valor = campo.placeholder;
        caja.classList.add("marcador");
      }
      caja.textContent = valor;
      if (estilo.textAlign === "right" || estilo.textAlign === "end") caja.classList.add("derecha");
      if (estilo.textAlign === "center") caja.classList.add("centro");
      campo.replaceWith(caja);
    });
  }

  window.__prepararCaptura = prepararCaptura; // usado por las pruebas de la vista previa

  // -------------------------------------------------------- ayudas y avisos
  let ayudaObjetivo = null;
  let ayudaTemporizador = null;

  function mostrarAyuda(objetivo) {
    const ayuda = $("#ayuda");
    ayuda.textContent = objetivo.dataset.ayuda;
    const caja = objetivo.getBoundingClientRect();
    ayuda.style.left = "0px";
    ayuda.style.top = "0px";
    ayuda.classList.add("visible");
    const ancho = ayuda.offsetWidth;
    const alto = ayuda.offsetHeight;
    let arriba = caja.bottom + 8;
    if (arriba + alto > window.innerHeight - 6) arriba = caja.top - alto - 8;
    const izquierda = Math.min(Math.max(6, caja.left + caja.width / 2 - ancho / 2), window.innerWidth - ancho - 6);
    ayuda.style.left = `${izquierda}px`;
    ayuda.style.top = `${arriba}px`;
  }

  function ocultarAyuda() {
    clearTimeout(ayudaTemporizador);
    ayudaObjetivo = null;
    $("#ayuda").classList.remove("visible");
  }

  document.addEventListener("mouseover", (evento) => {
    const objetivo = evento.target.closest("[data-ayuda]");
    if (objetivo === ayudaObjetivo) return;
    ocultarAyuda();
    if (!objetivo || !objetivo.dataset.ayuda) return;
    ayudaObjetivo = objetivo;
    ayudaTemporizador = setTimeout(() => mostrarAyuda(objetivo), RETARDO_AYUDA_MS);
  });
  document.addEventListener("mouseleave", ocultarAyuda);
  document.addEventListener("mousedown", ocultarAyuda, true);

  function avisar(mensaje, tipo = "info", duracion = 2600) {
    const contenedor = $("#avisos");
    while (contenedor.children.length >= 3) contenedor.firstElementChild.remove();
    const simbolo = tipo === "exito" ? "i-check" : tipo === "error" ? "i-alerta" : "i-alerta";
    const aviso = crear(`<div class="aviso ${tipo}" role="status">${icono(simbolo)}<span></span></div>`);
    texto($("span", aviso), mensaje);
    contenedor.append(aviso);
    setTimeout(() => {
      aviso.classList.add("saliendo");
      aviso.addEventListener("animationend", () => aviso.remove(), { once: true });
      setTimeout(() => aviso.remove(), 400);
    }, duracion);
  }

  // --------------------------------------------------------------- diálogos
  function abrirDialogo({ titulo, contenido, botones = [], cerrable = true, clase = "", icono: simbolo = "", botonCerrar = false, alTeclear = null, enfocar = null }) {
    const capa = crear('<div class="capa-modal"><div class="dialogo" role="dialog" aria-modal="true"><div class="cab-dialogo"><h2></h2></div><div class="contenido-dialogo"></div><div class="acciones"></div></div></div>');
    const dialogo = $(".dialogo", capa);
    if (clase) dialogo.classList.add(...clase.split(" "));
    texto($("h2", capa), titulo);
    if (simbolo) $(".cab-dialogo", capa).prepend(crear(icono(simbolo)));
    const zona = $(".contenido-dialogo", capa);
    if (typeof contenido === "string") zona.append(texto(document.createElement("p"), contenido));
    else if (contenido) zona.append(contenido);
    const anterior = document.activeElement;
    let cerrado = false;

    function cerrar() {
      if (cerrado) return;
      cerrado = true;
      dialogosAbiertos.splice(dialogosAbiertos.indexOf(cerrar), 1);
      capa.classList.add("cerrando");
      const retirar = () => capa.remove();
      capa.addEventListener("animationend", retirar, { once: true });
      setTimeout(retirar, 400);
      document.removeEventListener("keydown", teclas, true);
      if (anterior && document.contains(anterior)) anterior.focus();
    }

    function teclas(evento) {
      // Con dos ventanas abiertas, solo responde la de arriba.
      const abiertas = $$(".capa-modal:not(.cerrando)");
      if (abiertas[abiertas.length - 1] !== capa) return;
      if (alTeclear && alTeclear(evento, cerrar)) {
        evento.preventDefault();
      } else if (evento.key === "Escape" && cerrable) {
        evento.preventDefault();
        cerrar();
      } else if (evento.key === "Tab") {
        const enfocables = $$("button:not([disabled]), input", dialogo).filter((e) => e.offsetParent !== null);
        if (!enfocables.length) return;
        const primero = enfocables[0];
        const ultimo = enfocables[enfocables.length - 1];
        if (evento.shiftKey && document.activeElement === primero) {
          evento.preventDefault();
          ultimo.focus();
        } else if (!evento.shiftKey && document.activeElement === ultimo) {
          evento.preventDefault();
          primero.focus();
        }
      } else if (evento.ctrlKey && !["c", "v", "x", "a", "z", "y"].includes(evento.key.toLowerCase())) {
        evento.preventDefault(); // los atajos de la calculadora no actúan detrás de la ventana
      }
    }

    if (botonCerrar && cerrable) {
      const x = crear(`<button type="button" class="boton-icono cerrar-dialogo" aria-label="Cerrar" data-ayuda="Cerrar · Esc">${icono("i-cerrar")}</button>`);
      x.addEventListener("click", cerrar);
      $(".cab-dialogo", capa).append(x);
    }
    const botonesCreados = botones.map((definicion) => {
      const boton = texto(crear(`<button type="button" class="boton ${definicion.clase || "suave"}"></button>`), definicion.texto);
      if (definicion.atajo) boton.append(texto(crear('<span class="atajo-boton"></span>'), definicion.atajo));
      boton.addEventListener("click", () => (definicion.accion ? definicion.accion(cerrar, boton) : cerrar()));
      $(".acciones", capa).append(boton);
      return boton;
    });
    if (!botones.length) $(".acciones", capa).remove();
    document.addEventListener("keydown", teclas, true);
    dialogosAbiertos.push(cerrar);
    ocultarAyuda();
    document.body.append(capa);
    const principal = enfocar || $(".boton.primario", capa) || $("button", capa);
    if (principal) principal.focus();
    return { capa, dialogo, cerrar, botones: botonesCreados };
  }

  const dialogosAbiertos = [];

  function cerrarDialogos() {
    dialogosAbiertos.slice().reverse().forEach((cerrar) => cerrar());
  }

  function hayDialogo() {
    return Boolean($(".capa-modal:not(.cerrando)"));
  }

  /** Pregunta antes de algo que no se puede deshacer. Devuelve una promesa con true/false. */
  function confirmar({ titulo, mensaje, aceptar = "Aceptar", peligro = false }) {
    return new Promise((resolver) => {
      let respondido = false;
      const { capa } = abrirDialogo({
        titulo,
        contenido: mensaje,
        clase: "medio",
        botones: [
          { texto: "Cancelar", clase: "suave", accion: (cerrar) => { respondido = true; resolver(false); cerrar(); } },
          { texto: aceptar, clase: peligro ? "peligro" : "primario", accion: (cerrar) => { respondido = true; resolver(true); cerrar(); } },
        ],
      });
      new MutationObserver((_, observador) => {
        if (!document.body.contains(capa) || capa.classList.contains("cerrando")) {
          observador.disconnect();
          if (!respondido) resolver(false);
        }
      }).observe(capa, { attributes: true, attributeFilter: ["class"] });
    });
  }

  function mostrarNovedades(notas) {
    const contenido = document.createElement("div");
    notas.secciones.forEach((seccion) => {
      contenido.append(texto(document.createElement("h3"), seccion.titulo));
      const lista = document.createElement("ul");
      seccion.elementos.forEach((elemento) => {
        const item = crear('<li><span class="vineta"></span><span></span></li>');
        texto(item.firstElementChild, seccion.vineta);
        texto(item.lastElementChild, elemento);
        lista.append(item);
      });
      contenido.append(lista);
    });
    abrirDialogo({
      titulo: `¡Actualización v${notas.version}!`,
      contenido,
      botones: [{ texto: "Entendido", clase: "primario" }],
    });
  }

  async function revisarActualizacion() {
    const info = await api.buscar_actualizacion();
    if (!info || !info.version) return;
    abrirDialogo({
      titulo: "Actualización disponible",
      contenido: `Hay una versión nueva (${info.version}).\nTu versión es la ${info.actual}.\n\n¿Quieres actualizar ahora?`,
      botones: [
        { texto: "Ahora no", clase: "suave" },
        {
          texto: "Actualizar",
          clase: "primario",
          accion: (cerrar) => {
            cerrar();
            descargarActualizacion(info);
          },
        },
      ],
    });
  }

  function descargarActualizacion(info) {
    const contenido = crear('<div><div class="progreso"><div class="relleno"></div></div><div class="porcentaje">0 %</div></div>');
    const { cerrar } = abrirDialogo({
      titulo: `Descargando la versión ${info.version}…`,
      contenido,
      cerrable: false,
    });
    const relleno = $(".relleno", contenido);
    const porcentaje = $(".porcentaje", contenido);

    function fallo(mensaje) {
      cerrar();
      abrirDialogo({ titulo: "Actualización", contenido: mensaje, botones: [{ texto: "Entendido", clase: "primario" }] });
    }

    async function seguir(estado) {
      if (estado.estado === "error") {
        fallo(estado.mensaje);
        return;
      }
      const avance = Math.round((estado.progreso || 0) * 100);
      relleno.style.width = `${avance}%`;
      porcentaje.textContent = `${avance} %`;
      if (estado.estado === "listo") {
        porcentaje.textContent = "Instalando…";
        const resultado = await api.instalar_actualizacion();
        if (!resultado || !resultado.ok) fallo((resultado && resultado.mensaje) || "No se pudo instalar la actualización.");
        return;
      }
      setTimeout(async () => seguir(await api.estado_descarga()), SONDEO_DESCARGA_MS);
    }

    api.descargar_actualizacion().then(seguir);
  }


  // ------------------------------------------------------------- historial
  function estadoCompleto() {
    return { ...leerEstado(), con_descuento: $("#con-descuento").checked };
  }

  function ponerInsignia(cantidad) {
    const insignia = $("#insignia-historial");
    const antes = insignia.textContent;
    insignia.hidden = !cantidad;
    texto(insignia, String(cantidad || 0));
    if (antes !== insignia.textContent && !primeraVez) {
      insignia.classList.remove("salto");
      void insignia.offsetWidth;
      insignia.classList.add("salto");
    }
  }

  function hayDatos() {
    const personas = $$("#personas input").some((e) => (e.dataset.tipo === "ADULTOS" ? e.value !== "1" : e.value !== "0"));
    const montos = filas.some((fila) => Object.values(fila.entradas).some((e) => textoEditable(e.value) !== ""));
    return personas || montos || filas.some((fila) => !fila.fijo);
  }

  /** Vuelve a cargar en la calculadora una cotización guardada. */
  function restaurarEstado(estado) {
    cerrarFlotante(true);
    ocultarAyuda();
    const personas = estado.personas || {};
    $$("#personas input").forEach((entrada) => {
      const valor = parseInt(personas[entrada.dataset.tipo], 10);
      entrada.value = String(Number.isFinite(valor) ? Math.min(99, Math.max(0, valor)) : entrada.dataset.tipo === "ADULTOS" ? 1 : 0);
    });
    filas.filter((fila) => !fila.fijo).forEach((fila) => fila.elemento.remove());
    filas = filas.filter((fila) => fila.fijo);
    $$("#cuerpo-servicios .aviso-fila").forEach((franja) => franja.remove());
    filas.forEach((fila) => {
      Object.values(fila.entradas).forEach((entrada) => {
        entrada.value = "$ 0.00";
        entrada.classList.remove("invalido", "alerta");
      });
      Object.values(fila.marcas).forEach((casilla) => (casilla.checked = false));
    });
    $("#repartir").checked = Boolean(estado.repartir);
    pintarModoReparto();

    const usados = new Set();
    (estado.servicios || []).forEach((servicio) => {
      if (!servicio || !config.servicios[servicio.base]) return;
      let fila = filas.find((f) => f.fijo && f.base === servicio.base && !usados.has(f));
      if (!fila) fila = agregarFila(servicio.base, { enfocar: false, animar: false, calcular: false });
      usados.add(fila);
      if (fila.subtipo && servicio.subtipo) fila.subtipo.value = servicio.subtipo;
      Object.entries(servicio.incluye || {}).forEach(([tipo, valor]) => {
        if (fila.marcas[tipo]) fila.marcas[tipo].checked = Boolean(valor);
      });
      Object.entries(servicio.montos || {}).forEach(([clave, valor]) => {
        if (fila.entradas[clave]) fila.entradas[clave].value = String(valor || "$ 0.00");
      });
    });

    $("#redondear").checked = estado.redondear !== false;
    $("#con-descuento").checked = Boolean(estado.con_descuento);
    aplicarDescuento();
    $("#no-reembolsable").checked = Boolean(estado.no_reembolsable);
    $("#fecha-viaje").value = estado.fecha_viaje || "";
    $("#fecha-cancelacion").value = estado.fecha_cancelacion || "";
    $("#ajuste-nuevo").value = estado.ajuste_nuevo || "";
    actualizarColumnas();
    calcular(false);
  }

  let abriendoGuardar = false;

  async function abrirGuardar() {
    if (abriendoGuardar || hayDialogo()) return;
    abriendoGuardar = true;
    try {
      if (temporizador) await calcular(false);
      const estado = estadoCompleto();
      const previo = await api.preparar_guardado(estado);
      if (!previo || !previo.ok) {
        avisar((previo && previo.mensaje) || "Revisa la cotización antes de guardarla.", "error", 3500);
        return;
      }
      if (previo.monto_pvp <= 0) {
        avisar("La cotización está en $ 0.00: escribe los montos antes de guardarla.", "error", 3500);
        return;
      }
      mostrarGuardar(estado, previo);
    } finally {
      abriendoGuardar = false;
    }
  }

  function mostrarGuardar(estado, previo) {
    const servicios = previo.servicios.length ? ` · ${previo.servicios.join(", ")}` : "";
    const contenido = crear(`
      <div>
        <p class="sub"></p>
        <div class="form-campo">
          <label for="guardar-enlace">Enlace de negociación</label>
          <input class="campo" id="guardar-enlace" autocomplete="off" spellcheck="false" placeholder="Pega aquí el enlace de Bitrix24" />
          <span class="ayuda-campo" id="guardar-ayuda">Pega el enlace de la negociación.</span>
        </div>
        <div class="form-campo">
          <label for="guardar-referencia">Nombre de referencia <span>(opcional)</span></label>
          <input class="campo" id="guardar-referencia" autocomplete="off" maxlength="80" placeholder="Ej.: Familia López · Cancún" />
        </div>
        <div class="resumen-guardar">
          <div><div class="et"></div><div class="det"></div></div>
          <div><div class="grande"></div><div class="q"></div></div>
        </div>
      </div>`);
    const titulo = historialTitulo || "este mes";
    texto($(".sub", contenido), `Se guarda en el historial de ${titulo.toLowerCase()} con la configuración completa de la calculadora.`);
    texto($(".resumen-guardar .et", contenido), "Monto que se guarda · Total PVP");
    if (estado.con_descuento) $(".resumen-guardar .q", contenido).after(texto(crear('<div class="q"></div>'), `Con descuento ${previo.descuento}`));
    texto($(".resumen-guardar .det", contenido), `${previo.personas_texto}${servicios}`);
    texto($(".resumen-guardar .grande", contenido), previo.pvp);
    texto($(".resumen-guardar .q", contenido), previo.pvp_q);
    const enlace = $("#guardar-enlace", contenido);
    const referencia = $("#guardar-referencia", contenido);
    const ayuda = $("#guardar-ayuda", contenido);
    if (negociacionActual) {
      enlace.value = negociacionActual.enlace;
      referencia.value = negociacionActual.referencia;
    }

    let revision = 0;
    async function revisar() {
      const mia = ++revision;
      const r = await api.revisar_enlace(enlace.value);
      if (mia !== revision || !r) return;
      ayuda.className = `ayuda-campo ${r.tono}`;
      texto(ayuda, r.tono === "exito" ? `✓ ${r.mensaje}` : r.mensaje);
      enlace.classList.toggle("invalido", r.tono === "error");
      return r;
    }
    enlace.addEventListener("input", revisar);
    enlace.addEventListener("focus", () => enlace.select());
    if (enlace.value) revisar();

    let ocupado = false;
    async function guardar(cerrar, accion = "comprobar", id = null) {
      if (ocupado) return;
      const revisado = await revisar();
      if (!revisado || !revisado.valido) {
        enlace.classList.add("invalido");
        enlace.focus();
        return;
      }
      ocupado = true;
      try {
        const r = await api.guardar_negociacion({ enlace: enlace.value, referencia: referencia.value, estado, accion, id });
        if (r && r.ok) {
          cerrar();
          const reg = r.registro;
          negociacionActual = { id: reg.id, enlace: reg.enlace, negociacion: reg.negociacion, referencia: reg.referencia };
          avisar(r.actualizado ? "Negociación actualizada en el historial" : "Negociación guardada en el historial", "exito", 2200);
          refrescarInsignia();
        } else if (r && r.duplicado) {
          preguntarDuplicado(r, (nuevaAccion, idRepetido) => guardar(cerrar, nuevaAccion, idRepetido));
        } else {
          avisar((r && r.mensaje) || "No se pudo guardar.", "error", 3500);
          if (r && r.campo === "enlace") enlace.focus();
        }
      } finally {
        ocupado = false;
      }
    }

    abrirDialogo({
      titulo: "Guardar negociación",
      icono: "i-guardar",
      clase: "medio",
      contenido,
      enfocar: enlace.value ? referencia : enlace,
      botones: [
        { texto: "Cancelar", clase: "suave" },
        { texto: "Guardar", clase: "primario", atajo: "Ctrl+G", accion: (cerrar) => guardar(cerrar) },
      ],
      alTeclear: (evento, cerrar) => {
        const tecla = evento.key.toLowerCase();
        if ((evento.key === "Enter" && evento.target.tagName === "INPUT") || (evento.ctrlKey && tecla === "g")) {
          guardar(cerrar);
          return true;
        }
        return false;
      },
    });
  }

  function preguntarDuplicado(respuesta, elegir) {
    const repetido = respuesta.duplicado;
    const cuando = repetido.hoy ? `hoy a las ${repetido.hora}` : `el ${repetido.fecha} a las ${repetido.hora}`;
    const contenido = crear("<div><p></p><p class=\"sub\">Actualizar reemplaza el monto y la configuración guardada; no crea otra fila.</p></div>");
    const nombre = repetido.referencia || (repetido.negociacion ? `la negociación ${repetido.negociacion}` : "este enlace");
    texto($("p", contenido), `${nombre[0].toUpperCase()}${nombre.slice(1)} se guardó ${cuando} con ${repetido.monto}.\nAhora la calculadora tiene ${respuesta.nuevo_monto}.`);
    abrirDialogo({
      titulo: "Esta negociación ya está guardada",
      clase: "medio",
      contenido,
      botones: [
        { texto: "Cancelar", clase: "suave" },
        { texto: "Guardar como otra", clase: "suave", accion: (cerrar) => { cerrar(); elegir("nuevo"); } },
        { texto: "Actualizar", clase: "primario", accion: (cerrar) => { cerrar(); elegir("actualizar", repetido.id); } },
      ],
    });
  }

  async function refrescarInsignia() {
    const r = await api.historial_resumen();
    if (r && r.ok) {
      historialTitulo = r.titulo;
      ponerInsignia(r.cantidad);
    }
    return r;
  }

  function filaHistorial(registro, alCambiar) {
    const fila = crear(`
      <div class="fila-hist">
        <span class="hora"></span>
        <span class="ref"></span>
        <button type="button" class="enlace"><span></span>${icono("i-enlace")}</button>
        <span class="pers"></span>
        <div class="monto"><span class="copiable"></span><span class="linea-q"><span class="copiable"></span></span></div>
        <div class="acc">
          <button type="button" class="boton-icono reabrir" data-ayuda="Reabrir en la calculadora" aria-label="Reabrir en la calculadora">${icono("i-reabrir")}</button>
          <button type="button" class="boton-icono quitar" data-ayuda="Quitar del historial" aria-label="Quitar del historial">${icono("i-basura")}</button>
        </div>
      </div>`);
    texto($(".hora", fila), registro.hora);
    const ref = $(".ref", fila);
    texto(ref, registro.referencia || "Sin referencia");
    ref.classList.toggle("vacia", !registro.referencia);
    if (registro.referencia) ref.title = registro.referencia;
    const enlace = $(".enlace", fila);
    texto($("span", enlace), registro.negociacion ? `Negociación ${registro.negociacion}` : "Abrir enlace");
    enlace.dataset.ayuda = registro.enlace;
    enlace.addEventListener("click", async () => {
      const r = await api.abrir_enlace(registro.enlace);
      if (!r || !r.ok) avisar((r && r.mensaje) || "No se pudo abrir el enlace.", "error", 3000);
    });
    texto($(".pers", fila), registro.personas);
    const [usd, q] = $$(".copiable", fila);
    texto(usd, registro.monto);
    texto(q, registro.monto_q);
    if (registro.con_descuento) {
      const etiqueta = texto(crear('<span class="etq-desc"></span>'), "con descuento");
      etiqueta.dataset.ayuda = `Con descuento por pago en efectivo: ${registro.descuento}`;
      $(".linea-q", fila).prepend(etiqueta);
    }
    $(".reabrir", fila).addEventListener("click", () => reabrir(registro));
    $(".quitar", fila).addEventListener("click", async () => {
      const nombre = registro.referencia || (registro.negociacion ? `la negociación ${registro.negociacion}` : "esta negociación");
      const si = await confirmar({
        titulo: "¿Quitar del historial?",
        mensaje: `Se quitará ${nombre} (${registro.monto}) del historial de este mes.`,
        aceptar: "Quitar",
        peligro: true,
      });
      if (!si) return;
      const r = await api.quitar_negociacion(registro.id);
      if (!r || !r.ok) {
        avisar((r && r.mensaje) || "No se pudo quitar.", "error", 3000);
        return;
      }
      if (negociacionActual && negociacionActual.id === registro.id) negociacionActual = null;
      fila.classList.add("saliendo");
      setTimeout(alCambiar, 180);
    });
    fila.dataset.busqueda = [registro.referencia, registro.negociacion, registro.enlace, registro.personas, registro.monto, registro.hora]
      .join(" ")
      .toLowerCase();
    return fila;
  }

  async function reabrir(registro) {
    const r = await api.abrir_negociacion(registro.id);
    if (!r || !r.ok) {
      avisar((r && r.mensaje) || "No se pudo abrir.", "error", 3000);
      return;
    }
    const mismo = negociacionActual && negociacionActual.id === r.id;
    if (hayDatos() && !mismo) {
      const si = await confirmar({
        titulo: "¿Reabrir esta cotización?",
        mensaje: "Lo que tienes ahora en la calculadora se reemplazará. Si lo necesitas, guárdalo antes.",
        aceptar: "Reabrir",
      });
      if (!si) return;
    }
    cerrarDialogos();
    restaurarEstado(r.estado || {});
    negociacionActual = { id: r.id, enlace: r.enlace, negociacion: r.negociacion, referencia: r.referencia };
    const nombre = r.referencia || (r.negociacion ? `Negociación ${r.negociacion}` : "Cotización");
    avisar(`${nombre} cargada en la calculadora`, "exito", 2200);
  }

  function esqueletoHistorial() {
    const lista = crear('<div class="lista-hist"></div>');
    [70, 100, 100, 100, 60, 100, 100].forEach((ancho, i) =>
      lista.append(crear(`<div class="barra-esqueleto ${i % 3 ? "alta" : ""}" style="width:${ancho}%"></div>`))
    );
    return lista;
  }

  async function abrirHistorial() {
    if (hayDialogo()) return;
    const contenido = crear(`
      <div class="contenido-historial" style="display:contents">
        <div class="chips">
          <div class="chip-dato"><div class="et">Negociaciones</div><div class="v" id="hist-cantidad">—</div></div>
          <div class="chip-dato"><div class="et">Total del mes</div><div class="v"><span class="copiable" id="hist-total">—</span><small class="copiable" id="hist-total-q"></small></div></div>
          <div class="chip-dato"><div class="et">Hoy</div><div class="v"><span id="hist-hoy">—</span><small class="copiable" id="hist-hoy-total"></small></div></div>
        </div>
        <div class="barra-hist">
          <label class="buscar">${icono("i-buscar")}<input class="campo" id="hist-buscar" autocomplete="off" placeholder="Buscar por referencia, número o monto" /></label>
          <span class="espacio"></span>
          <button type="button" class="boton suave" id="hist-carpeta">${icono("i-carpeta")}Abrir carpeta</button>
          <button type="button" class="boton suave" id="hist-excel">${icono("i-excel")}Exportar a Excel</button>
        </div>
        <div class="aviso-reinicio" id="hist-reinicio">${icono("i-alerta")}<span></span></div>
      </div>`);
    let lista = esqueletoHistorial();
    contenido.append(lista);
    const { dialogo } = abrirDialogo({
      titulo: "Historial",
      icono: "i-reloj",
      clase: "ancho",
      contenido,
      botonCerrar: true,
      enfocar: $("#hist-buscar", contenido),
      alTeclear: (evento) => {
        if (evento.ctrlKey && evento.key.toLowerCase() === "h") return true;
        return false;
      },
    });
    const buscar = $("#hist-buscar", contenido);
    $("#hist-carpeta", contenido).addEventListener("click", () => api.abrir_carpeta("raiz"));
    $("#hist-excel", contenido).addEventListener("click", async (evento) => {
      const boton = evento.currentTarget;
      boton.disabled = true;
      const r = await api.exportar_historial();
      boton.disabled = false;
      if (r && r.ok) avisar(`Excel creado · ${r.archivo}`, "exito", 3200);
      else avisar((r && r.mensaje) || "No se pudo crear el Excel.", "error", 4000);
    });

    async function cargar() {
      const r = await refrescarInsignia();
      if (!document.body.contains(dialogo)) return;
      if (!r || !r.ok) {
        avisar((r && r.mensaje) || "No se pudo leer el historial.", "error", 4000);
        return;
      }
      texto($("h2", dialogo), `Historial · ${r.titulo}`);
      texto($("#hist-cantidad", contenido), String(r.cantidad));
      texto($("#hist-total", contenido), r.total);
      texto($("#hist-total-q", contenido), r.total_q);
      texto($("#hist-hoy", contenido), String(r.hoy_cantidad));
      texto($("#hist-hoy-total", contenido), r.hoy_total);
      const reinicio = $("#hist-reinicio", contenido);
      reinicio.classList.toggle("problema", Boolean(r.aviso));
      $("span", reinicio).innerHTML = "";
      if (r.aviso) texto($("span", reinicio), r.aviso);
      else {
        $("span", reinicio).append("El ", texto(document.createElement("b"), r.reinicio), " se guarda una copia en Excel de este mes y el historial empieza de nuevo.");
      }

      const nueva = crear('<div class="lista-hist"></div>');
      if (!r.cantidad) {
        nueva.append(crear(`<div class="vacio-hist">${icono("i-reloj")}<div>Todavía no hay negociaciones este mes.</div><div>Usa <b>Guardar</b> o <kbd>Ctrl</kbd>+<kbd>G</kbd> para agregar la primera.</div></div>`));
      } else {
        nueva.append(crear('<div class="fila-hist encab-hist"><span>Hora</span><span>Referencia</span><span>Enlace de negociación</span><span>Personas</span><span style="text-align:right">Monto</span><span></span></div>'));
        r.dias.forEach((dia) => {
          const grupo = crear('<div class="grupo-dia"><div class="dia-hist"><b></b><span class="cuenta"></span><span class="tot copiable"></span></div></div>');
          texto($("b", grupo), dia.titulo);
          texto($(".cuenta", grupo), `${dia.cantidad} ${dia.cantidad === 1 ? "negociación" : "negociaciones"}`);
          texto($(".tot", grupo), dia.total);
          dia.registros.forEach((registro) => grupo.append(filaHistorial(registro, cargar)));
          nueva.append(grupo);
        });
        nueva.append(crear('<div class="vacio-hist sin-resultados" hidden>No hay negociaciones que coincidan con la búsqueda.</div>'));
      }
      lista.replaceWith(nueva);
      lista = nueva;
      filtrar();
    }

    function filtrar() {
      const termino = buscar.value.trim().toLowerCase();
      let visibles = 0;
      $$(".grupo-dia", lista).forEach((grupo) => {
        let enGrupo = 0;
        $$(".fila-hist", grupo).forEach((fila) => {
          const ver = !termino || fila.dataset.busqueda.includes(termino);
          fila.hidden = !ver;
          if (ver) enGrupo += 1;
        });
        grupo.hidden = !enGrupo;
        visibles += enGrupo;
      });
      const sinResultados = $(".sin-resultados", lista);
      if (sinResultados) sinResultados.hidden = visibles > 0;
    }
    buscar.addEventListener("input", filtrar);
    cargar();
  }

  function abrirFunciones() {
    if (hayDialogo()) return;
    const atajo = (...teclas) => teclas.map((t) => `<kbd>${t}</kbd>`).join("+");
    const funciones = [
      ["i-camara", "Tomar captura", `Copia la calculadora completa como imagen y la guarda en la carpeta Capturas con fecha, referencia, personas y monto. ${atajo("Ctrl", "Shift", "S")}`],
      ["i-guardar", "Guardar negociación", `Guarda el enlace de Bitrix24, una referencia opcional, el Total PVP y toda la configuración. ${atajo("Ctrl", "G")}`],
      ["i-reloj", "Historial", `Negociaciones del mes por día. Abre el enlace o copia montos con un clic, y reabre cualquier cotización. El día 2 de cada mes se guarda un Excel y empieza de nuevo. ${atajo("Ctrl", "H")}`],
      ["i-reparto", "Repartir monto", `Para cotizaciones atípicas: escribes un solo total por servicio y se reparte adulto ${config.pesos_reparto.ADULTOS} · niño ${config.pesos_reparto["NIÑOS"]} · infante ${config.pesos_reparto.INFANTES}.`],
      ["i-redondear", "Redondear", "Redondea cada precio por persona al entero más cercano (50.49 → 50, 50.50 → 51)."],
      ["i-etiqueta", "PVP con descuento", "Muestra también el precio por pago único en efectivo (PVP ÷ 1.05)."],
      ["i-intercambiar", "Conversión", `Convierte quetzales a dólares o al revés con el botón ⇄, a ${config.tipo_cambio}. No cambia el presupuesto.`],
      ["i-copiar", "Copiar con un clic", "Toca cualquier cifra en dólares o quetzales para copiarla tal como se ve."],
      ["i-lista", "Desglose", "Costo y PVP de cada servicio. Siempre sale en la captura, aunque esté plegado."],
      ["i-calendario", "Fecha de pago", "Con la fecha de viaje y la de cancelación del hotel calcula cuándo pagar, y avisa de fechas que no existen o ya pasaron."],
      ["i-moneda", "Monto para reservar", "Total de boletos del grupo completo ÷ 0.80, listo para copiar."],
      ["i-ajuste", "Ajuste de diseñador", "Escribe el precio por adulto que quieres ofrecer y ve la diferencia contra el actual."],
    ];
    const contenido = crear(`
      <div class="contenido-funciones">
        <div class="funciones-grid"></div>
        <h3 class="seccion-f">Atajos de teclado</h3>
        <div class="tabla-atajos">
          <span>${atajo("Ctrl", "Enter")}</span><span>Calcular</span><span>${atajo("Ctrl", "G")}</span><span>Guardar negociación</span>
          <span>${atajo("Ctrl", "Shift", "S")}</span><span>Tomar captura</span><span>${atajo("Ctrl", "H")}</span><span>Abrir historial</span>
          <span>${atajo("Ctrl", "L")}</span><span>Limpiar todo</span><span>${atajo("Enter")}</span><span>Pasar al siguiente campo</span>
          <span>${atajo("F1")}</span><span>Abrir esta ventana</span><span>${atajo("Esc")}</span><span>Cerrar ventanas</span>
        </div>
        <h3 class="seccion-f">Carpeta de la calculadora</h3>
        <div class="carpeta-f">${icono("i-carpeta")}<b>Documentos › Calculadora D&amp;T</b><span>Historial, Capturas (por mes) y Respaldos Excel</span>
          <button type="button" class="boton suave" id="funciones-carpeta">Abrir carpeta</button></div>
      </div>`);
    const rejilla = $(".funciones-grid", contenido);
    funciones.forEach(([simbolo, titulo, descripcion]) => {
      const tarjeta = crear(`<div class="funcion"><span class="ic">${icono(simbolo)}</span><b></b><p>${descripcion}</p></div>`);
      texto($("b", tarjeta), titulo);
      rejilla.append(tarjeta);
    });
    $("#funciones-carpeta", contenido).addEventListener("click", () => api.abrir_carpeta("raiz"));
    abrirDialogo({
      titulo: "Funciones de la calculadora",
      icono: "i-funciones",
      clase: "ancho",
      contenido,
      botonCerrar: true,
      alTeclear: (evento) => evento.key === "F1",
    });
  }

  // ---------------------------------------------------------------- eventos
  function conectarEventos() {
    $("#agregar-servicio").addEventListener("click", abrirMenuServicios);
    $("#boton-calcular").addEventListener("click", () => calcular(true));
    $("#boton-limpiar").addEventListener("click", limpiar);
    $("#boton-captura").addEventListener("click", capturar);
    $("#boton-guardar").addEventListener("click", abrirGuardar);
    $("#boton-historial").addEventListener("click", abrirHistorial);
    $("#boton-funciones").addEventListener("click", abrirFunciones);
    $("#enlace-carpeta").addEventListener("click", () => api.abrir_carpeta("raiz"));
    document.addEventListener("click", (evento) => {
      const cifra = evento.target.closest(".copiable");
      if (cifra && !window.getSelection().toString()) copiarCifra(cifra);
    });
    $("#boton-desglose").addEventListener("click", alternarDesglose);
    $("#redondear").addEventListener("change", () => calcular(false));
    $("#repartir").addEventListener("change", () => aplicarReparto());
    $("#con-descuento").addEventListener("change", aplicarDescuento);
    $("#no-reembolsable").addEventListener("change", () => calcular(false));

    ["fecha-viaje", "fecha-cancelacion"].forEach((id) => {
      const entrada = $(`#${id}`);
      entrada.addEventListener("input", () => {
        const nuevo = conDiagonales(entrada.value);
        if (nuevo !== entrada.value) entrada.value = nuevo;
        programarCalculo();
      });
      entrada.addEventListener("keydown", (evento) => {
        if (evento.key === "Enter" && !evento.ctrlKey) {
          evento.preventDefault();
          calcular(false);
        }
      });
      entrada.addEventListener("blur", () => calcular(false));
    });
    $$("[data-calendario]").forEach((boton) =>
      boton.addEventListener("click", () => abrirCalendario($(`#${boton.dataset.calendario}`), boton))
    );

    // Convertidor Q <-> $: aparte del presupuesto
    const conversion = $("#herramienta-conversion");
    const montoConvertir = $("#convertir-q");
    const intercambiar = $("#convertir-intercambiar");
    let convirtiendo = 0;
    async function convertir() {
      const mia = ++convirtiendo;
      const respuesta = await api.convertir_moneda(montoConvertir.value, conversion.dataset.origen);
      if (mia !== convirtiendo || !respuesta) return;
      montoConvertir.classList.toggle("invalido", !respuesta.valido);
      poner($("#convertir-usd"), respuesta.resultado);
    }
    function describirConversion() {
      const deDolares = conversion.dataset.origen === "USD";
      texto($("#convertir-prefijo"), deDolares ? "$" : "Q");
      intercambiar.setAttribute("aria-label", deDolares ? "Cambiar a quetzales → dólares" : "Cambiar a dólares → quetzales");
      intercambiar.dataset.ayuda = deDolares ? "Ahora: dólares → quetzales. Clic para invertir" : "Ahora: quetzales → dólares. Clic para invertir";
      conversion.dataset.ayuda = `${deDolares ? "Dólares a quetzales" : "Quetzales a dólares"} (tipo de cambio ${config.tipo_cambio}) · solo para consultar, no cambia el presupuesto`;
    }
    window.__ponerOrigenConversion = (origen) => {
      conversion.dataset.origen = origen;
      describirConversion();
    };
    montoConvertir.addEventListener("input", convertir);
    montoConvertir.addEventListener("focus", () => montoConvertir.select());
    montoConvertir.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter") montoConvertir.blur();
    });
    intercambiar.addEventListener("click", () => {
      conversion.dataset.origen = conversion.dataset.origen === "USD" ? "GTQ" : "USD";
      conversion.classList.remove("girando");
      void conversion.offsetWidth;
      conversion.classList.add("girando");
      describirConversion();
      convertir();
    });
    conversion.addEventListener("animationend", () => conversion.classList.remove("girando"));
    describirConversion();

    const ajuste = $("#ajuste-nuevo");
    conectarMonto(ajuste, null, () => programarCalculo(), true);

    document.addEventListener("keydown", (evento) => {
      if (hayDialogo()) return;
      const tecla = evento.key.toLowerCase();
      const atajo =
        evento.key === "F1" ? abrirFunciones
        : evento.ctrlKey && evento.shiftKey && tecla === "s" ? capturar
        : evento.ctrlKey && !evento.shiftKey && tecla === "g" ? abrirGuardar
        : evento.ctrlKey && !evento.shiftKey && tecla === "h" ? abrirHistorial
        : evento.ctrlKey && !evento.shiftKey && tecla === "l" ? limpiar
        : null;
      if (atajo) {
        evento.preventDefault();
        cerrarFlotante(true);
        atajo();
        return;
      }
      if (evento.key === "Enter" && evento.ctrlKey) {
        evento.preventDefault();
        if (document.activeElement && document.activeElement.classList.contains("monto")) {
          formatear(document.activeElement, document.activeElement.id === "ajuste-nuevo");
        }
        calcular(true);
      } else if (evento.key === "Escape" && flotante) {
        const ancla = flotante.ancla;
        cerrarFlotante();
        ancla.focus();
      }
    });
    document.addEventListener("mousedown", (evento) => {
      if (flotante && !flotante.elemento.contains(evento.target) && !flotante.ancla.contains(evento.target)) {
        cerrarFlotante();
      }
    });
    $("#principal").addEventListener("scroll", () => {
      cerrarFlotante();
      ocultarAyuda();
    });
    window.addEventListener("resize", () => cerrarFlotante(true));
  }
})();
