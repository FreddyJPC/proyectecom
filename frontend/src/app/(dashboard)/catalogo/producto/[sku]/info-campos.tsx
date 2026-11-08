import { InfoButton, InfoEjemplo } from "@/components/app/info-button";

/**
 * Las explicaciones ⓘ de los campos de un producto. Viven aquí porque el mismo campo aparece en la ficha de un
 * producto y en el formulario de «Publicar producto propio»: así el texto se escribe una sola vez y no se desfasa.
 */

export function InfoDescripcion() {
  return (
    <InfoButton titulo="Descripción">
      <p>Qué es el producto, para qué sirve y qué incluye.</p>
      <p>
        Escribe <strong>solo lo que sabes que es cierto</strong>: Victoria lo repetirá tal cual al cliente.
      </p>
    </InfoButton>
  );
}

export function InfoVariantes() {
  return (
    <InfoButton titulo="Variantes">
      <p>Los colores, tallas o modelos disponibles, separados por comas.</p>
      <InfoEjemplo>
        <p>Negro, Blanco, Azul</p>
      </InfoEjemplo>
      <p>Si el producto tiene variantes, Victoria le pregunta al cliente cuál prefiere.</p>
    </InfoButton>
  );
}

export function InfoPreguntasFrecuentes() {
  return (
    <InfoButton titulo="Preguntas frecuentes">
      <p>
        Escribe la pregunta y su respuesta. Así Victoria contesta con <strong>tu información</strong> y no con suposiciones.
      </p>
      <InfoEjemplo>
        <p>¿Trae cargador? Sí, cable USB-C incluido.</p>
      </InfoEjemplo>
    </InfoButton>
  );
}

export function InfoTemasNoResponder() {
  return (
    <InfoButton titulo="Temas que Victoria NO debe responder">
      <p>Cosas sobre las que no quieres que opine ni prometa nada: Victoria sabe que no debe responder sobre ellas.</p>
      <InfoEjemplo>
        <p>Garantías que no ofreces, usos médicos, devoluciones.</p>
      </InfoEjemplo>
    </InfoButton>
  );
}

export function InfoTiempoEntrega() {
  return (
    <InfoButton titulo="Tiempo de entrega">
      <p>
        Es <strong>exactamente</strong> lo que Victoria le dirá al cliente sobre cuánto demora: no promete ningún otro plazo. Es obligatorio para publicar.
      </p>
    </InfoButton>
  );
}

export function InfoMaxUnidades() {
  return (
    <InfoButton titulo="Unidades máximas por pedido">
      <p>Cuántas unidades puede comprar una persona en un solo pedido. Si pide más, Victoria le explica el máximo.</p>
      <p>Lo comprueba el sistema, no la IA: un cliente no puede saltarse este límite.</p>
    </InfoButton>
  );
}

export function InfoMetodosPago() {
  return (
    <InfoButton titulo="Métodos de pago">
      <p>Los que Victoria puede ofrecerle al cliente para este producto. Elige al menos uno.</p>
      <ul>
        <li>
          <strong>Contraentrega:</strong> el cliente paga al recibir.
        </li>
        <li>
          <strong>Transferencia:</strong> pago anticipado. Tú pasas los datos de la cuenta y verificas el comprobante: Victoria no da cuentas ni confirma pagos.
        </li>
      </ul>
    </InfoButton>
  );
}

export function InfoCategoria() {
  return (
    <InfoButton titulo="Categoría">
      <p>El tipo de producto: calzado, ropa, electrónica… Crea las que necesites.</p>
      <p>Sirve para saber después qué tipo de producto te deja más. Victoria no la usa con los clientes.</p>
    </InfoButton>
  );
}

export function InfoCostoPropio() {
  return (
    <InfoButton titulo="Lo que te cuesta">
      <p>
        Lo que te cuesta <strong>una unidad</strong>. Con esto se calcula tu ganancia real en cada venta. Victoria no lo ve ni lo menciona.
      </p>
    </InfoButton>
  );
}

export function InfoControlaStock() {
  return (
    <InfoButton titulo="Llevar la cuenta de las unidades">
      <p>
        <strong>Encendido:</strong> cada venta descuenta del stock y, cuando llega a cero, el producto se pausa solo y Victoria deja de ofrecerlo. Si cancelas una venta, las unidades vuelven.
      </p>
      <p>
        <strong>Apagado:</strong> Victoria siempre lo ofrece como disponible, sin llevar la cuenta. Úsalo si fabricas bajo pedido o no quieres llevar la cuenta.
      </p>
    </InfoButton>
  );
}
