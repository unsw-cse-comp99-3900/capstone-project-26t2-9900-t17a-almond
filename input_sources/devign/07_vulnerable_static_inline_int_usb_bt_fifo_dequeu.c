static inline int usb_bt_fifo_dequeue(struct usb_hci_in_fifo_s *fifo,

                USBPacket *p)

{

    int len;



    if (likely(!fifo->len))

        return USB_RET_STALL;



    len = MIN(p->len, fifo->fifo[fifo->start].len);

    memcpy(p->data, fifo->fifo[fifo->start].data, len);

    if (len == p->len) {

        fifo->fifo[fifo->start].len -= len;

        fifo->fifo[fifo->start].data += len;

    } else {

        fifo->start ++;

        fifo->start &= CFIFO_LEN_MASK;

        fifo->len --;

    }



    fifo->dstart += len;

    fifo->dlen -= len;

    if (fifo->dstart >= fifo->dsize) {

        fifo->dstart = 0;

        fifo->dsize = DFIFO_LEN_MASK + 1;

    }



    return len;

}
