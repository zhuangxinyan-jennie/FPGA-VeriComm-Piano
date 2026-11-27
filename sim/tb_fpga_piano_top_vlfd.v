// Testbench for fpga_piano_top_vlfd.
// The sequence models PC keyboard notes A, S, and D:
//   A -> key_id=0 (C), 261 Hz
//   S -> key_id=2 (D), 293 Hz
//   D -> key_id=4 (E), 311 Hz
// Timing follows pc_keyboard/fifo_sequence.py: stable idle cycles,
// a one-cycle strobe pulse, then additional idle cycles for settled feedback.

`timescale 1ns / 1ps

module tb_fpga_piano_top_vlfd;

  parameter real CLK_HALF = 5.0; // 10 ns period, 100 MHz clock

  reg        clk = 1'b0;
  reg        rst_n;
  reg [3:0]  vc_key_id;
  reg        vc_key_on;
  reg        vc_cmd_strobe;

  wire [11:0] led;
  wire [15:0] out_freq_hz;
  wire [15:0] out_last_event_ts;

  always #(CLK_HALF) clk = ~clk;

  fpga_piano_top_vlfd dut (
      .clk(clk),
      .rst_n(rst_n),
      .vc_key_id(vc_key_id),
      .vc_key_on(vc_key_on),
      .vc_cmd_strobe(vc_cmd_strobe),
      .led(led),
      .out_freq_hz(out_freq_hz),
      .out_last_event_ts(out_last_event_ts)
  );

  task vlfd_issue_cmd;
    input [3:0] kid;
    input       on;
    integer     j;
    begin
      vc_key_id     = kid;
      vc_key_on     = on;
      vc_cmd_strobe = 1'b0;
      for (j = 0; j < 4; j = j + 1) @(posedge clk);
      vc_cmd_strobe = 1'b1;
      @(posedge clk);
      vc_cmd_strobe = 1'b0;
      @(posedge clk);
      for (j = 0; j < 8; j = j + 1) @(posedge clk);
    end
  endtask

  initial begin
    rst_n         = 1'b0;
    vc_key_id     = 4'd0;
    vc_key_on     = 1'b0;
    vc_cmd_strobe = 1'b0;
    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);

`ifdef DUMP_VCD
    $dumpfile("fpga_piano_tb.vcd");
    $dumpvars(0, tb_fpga_piano_top_vlfd);
`endif

    $display("=== KEY A (id=0) ON ===");
    vlfd_issue_cmd(4'd0, 1);
    $display("time=%0t led=%b freq=%0d", $time, led, out_freq_hz);

    $display("=== KEY A OFF ===");
    vlfd_issue_cmd(4'd0, 0);
    $display("time=%0t led=%b freq=%0d", $time, led, out_freq_hz);

    repeat (20) @(posedge clk);

    $display("=== KEY S (id=2) ON ===");
    vlfd_issue_cmd(4'd2, 1);
    $display("time=%0t led=%b freq=%0d", $time, led, out_freq_hz);

    $display("=== KEY S OFF ===");
    vlfd_issue_cmd(4'd2, 0);
    $display("time=%0t led=%b freq=%0d", $time, led, out_freq_hz);

    repeat (20) @(posedge clk);

    $display("=== KEY D (id=4) ON ===");
    vlfd_issue_cmd(4'd4, 1);
    $display("time=%0t led=%b freq=%0d", $time, led, out_freq_hz);

    $display("=== KEY D OFF ===");
    vlfd_issue_cmd(4'd4, 0);
    $display("time=%0t led=%b freq=%0d", $time, led, out_freq_hz);

    repeat (50) @(posedge clk);
    $display("=== TB done ===");
    $finish;
  end

endmodule
