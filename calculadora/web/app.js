/* Calculadora de viajes D&T — comportamiento de la pantalla.
   Los cálculos y formatos vienen de Python (window.pywebview.api); aquí solo se
   arma la interfaz, se leen los campos y se muestran los resultados. */
"use strict";

(() => {
  const CLAVES = ["adultos", "adultos_ninos", "adultos_ninos_infantes"];
  const TIPO_DE_CLAVE = { adultos_ninos: "NIÑOS", adultos_ninos_infantes: "INFANTES" };
  const CLASE_COLUMNA = { adultos: "col-adultos", adultos_ninos: "col-ninos", adultos_ninos_infantes: "col-infantes" };
  const NOMBRE_SINGULAR = { ADULTOS: "Adulto", "NIÑOS": "Niño", INFANTES: "Infante" };
  const NOTA_NORMAL =
    "Escribe el monto total de cada grupo · Diseñador: precio por persona · En Misceláneos marca la casilla para incluir niños o infantes";
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

  /** Enciende o apaga "Repartir monto". Al encender, si el total está vacío se copia el
      monto del grupo completo (la última columna activa) para no volver a escribirlo. */
  function aplicarReparto(recalcular = true) {
    const encendido = repartiendo();
    $("#tabla-servicios").classList.toggle("repartir", encendido);
    const pesos = config.pesos_reparto || {};
    texto(
      $("#nota-servicios"),
      encendido
        ? `Escribe el total del grupo completo (Diseñador: precio por persona) · Se reparte por persona: adulto ${pesos.ADULTOS} · niño ${pesos["NIÑOS"]} · infante ${pesos.INFANTES}`
        : NOTA_NORMAL
    );
    if (encendido) {
      const clave = activo("INFANTES") ? "adultos_ninos_infantes" : activo("NIÑOS") ? "adultos_ninos" : "adultos";
      filas.forEach((fila) => {
        const total = fila.entradas.total;
        if (textoEditable(total.value) === "" && textoEditable(fila.entradas[clave].value) !== "") {
          total.value = fila.entradas[clave].value;
        }
      });
    }
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
          <div class="valor precio col-pvp" data-campo="pvp">$ 0.00</div>
          <div class="valor precio col-desc"><span data-campo="descuento">$ 0.00</span></div>
          <div class="cantidad" data-campo="cantidad">× 0</div>
          <div class="valor secundario col-pvp" data-campo="pvp_q">Q 0.00</div>
          <div class="valor secundario col-desc"><span data-campo="descuento_q">Q 0.00</span></div>
          <div></div>
          <div class="valor secundario col-pvp" data-campo="pvp_total">Total $ 0.00</div>
          <div class="valor secundario col-desc"><span data-campo="descuento_total">Total $ 0.00</span></div>
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
    const aviso = $("#aviso-pago");
    if (!pago.visible) return;
    aviso.className = `aviso-pago ${pago.tono}`;
    poner(aviso, pago.texto);
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
    medirDescuento();
    dibujarDesglose(resultado.desglose);
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
      const respuesta = await api.copiar_captura(lienzo.toDataURL("image/png"));
      if (respuesta && respuesta.ok) {
        avisar("Captura copiada al portapapeles", "exito", 1800);
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
  function abrirDialogo({ titulo, contenido, botones = [], cerrable = true }) {
    const capa = crear('<div class="capa-modal"><div class="dialogo" role="dialog" aria-modal="true"><h2></h2><div class="contenido-dialogo"></div><div class="acciones"></div></div></div>');
    const dialogo = $(".dialogo", capa);
    texto($("h2", capa), titulo);
    const zona = $(".contenido-dialogo", capa);
    if (typeof contenido === "string") zona.append(texto(document.createElement("p"), contenido));
    else if (contenido) zona.append(contenido);
    const anterior = document.activeElement;
    let cerrado = false;

    function cerrar() {
      if (cerrado) return;
      cerrado = true;
      capa.classList.add("cerrando");
      const retirar = () => capa.remove();
      capa.addEventListener("animationend", retirar, { once: true });
      setTimeout(retirar, 400);
      document.removeEventListener("keydown", teclas, true);
      if (anterior && document.contains(anterior)) anterior.focus();
    }

    function teclas(evento) {
      if (evento.key === "Escape" && cerrable) {
        evento.preventDefault();
        cerrar();
      } else if (evento.key === "Tab") {
        const enfocables = $$("button, input", dialogo);
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
      }
      evento.stopPropagation();
    }

    botones.forEach((definicion) => {
      const boton = texto(crear(`<button type="button" class="boton ${definicion.clase || "suave"}"></button>`), definicion.texto);
      boton.addEventListener("click", () => (definicion.accion ? definicion.accion(cerrar) : cerrar()));
      $(".acciones", capa).append(boton);
    });
    if (!botones.length) $(".acciones", capa).remove();
    document.addEventListener("keydown", teclas, true);
    document.body.append(capa);
    const principal = $(".boton.primario", capa) || $("button", capa);
    if (principal) principal.focus();
    return { capa, dialogo, cerrar };
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

  // ---------------------------------------------------------------- eventos
  function conectarEventos() {
    $("#agregar-servicio").addEventListener("click", abrirMenuServicios);
    $("#boton-calcular").addEventListener("click", () => calcular(true));
    $("#boton-limpiar").addEventListener("click", limpiar);
    $("#boton-captura").addEventListener("click", capturar);
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
    });
    $$("[data-calendario]").forEach((boton) =>
      boton.addEventListener("click", () => abrirCalendario($(`#${boton.dataset.calendario}`), boton))
    );

    const ajuste = $("#ajuste-nuevo");
    conectarMonto(ajuste, null, () => programarCalculo(), true);

    document.addEventListener("keydown", (evento) => {
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
