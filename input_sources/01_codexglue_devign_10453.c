static int uhci_handle_td(UHCIState *s, uint32_t addr, UHCI_TD *td, uint32_t *int_mask)

{

    UHCIAsync *async;

    int len = 0, max_len;

    uint8_t pid;

    USBDevice *dev;

    USBEndpoint *ep;



    /* Is active ? */

    if (!(td->ctrl & TD_CTRL_ACTIVE))

        return TD_RESULT_NEXT_QH;



    async = uhci_async_find_td(s, addr, td);

    if (async) {

        /* Already submitted */

        async->queue->valid = 32;



        if (!async->done)

            return TD_RESULT_ASYNC_CONT;



        uhci_async_unlink(async);

        goto done;

    }



    /* Allocate new packet */

    async = uhci_async_alloc(uhci_queue_get(s, td), addr);

    if (!async)

        return TD_RESULT_NEXT_QH;



    /* valid needs to be large enough to handle 10 frame delay

     * for initial isochronous requests

     */

    async->queue->valid = 32;

    async->isoc  = td->ctrl & TD_CTRL_IOS;



    max_len = ((td->token >> 21) + 1) & 0x7ff;

    pid = td->token & 0xff;



    dev = uhci_find_device(s, (td->token >> 8) & 0x7f);

    ep = usb_ep_get(dev, pid, (td->token >> 15) & 0xf);

    usb_packet_setup(&async->packet, pid, ep);

    qemu_sglist_add(&async->sgl, td->buffer, max_len);

    usb_packet_map(&async->packet, &async->sgl);



    switch(pid) {

    case USB_TOKEN_OUT:

    case USB_TOKEN_SETUP:

        len = usb_handle_packet(dev, &async->packet);

        if (len >= 0)

            len = max_len;

        break;



    case USB_TOKEN_IN:

        len = usb_handle_packet(dev, &async->packet);

        break;



    default:

        /* invalid pid : frame interrupted */

        uhci_async_free(async);

        s->status |= UHCI_STS_HCPERR;

        uhci_update_irq(s);

        return TD_RESULT_STOP_FRAME;

    }

 

    if (len == USB_RET_ASYNC) {

        uhci_async_link(async);

        return TD_RESULT_ASYNC_START;

    }



    async->packet.result = len;



done:

    len = uhci_complete_td(s, td, async, int_mask);

    usb_packet_unmap(&async->packet);

    uhci_async_free(async);

    return len;

}
